// **********************************************************************
//
// Copyright (c) 2002
// Mutable Realms, Inc.
// Huntsville, AL, USA
//
// All Rights Reserved
//
// **********************************************************************

#include <IcePatch/Util.h>
#include <fstream>
#include <sys/stat.h>
#include <openssl/md5.h>
#include <bzlib.h>

#ifdef _WIN32
#   include <direct.h>
#   include <io.h>
#   define S_ISDIR(mode) ((mode) & _S_IFDIR)
#   define S_ISREG(mode) ((mode) & _S_IFREG)
#else
#   include <unistd.h>
#   include <dirent.h>
#endif

//
// Stupid Visual C++ defines min and max as macros :-(
//
#ifdef min
#   undef min
#endif
#ifdef max
#   undef max
#endif

using namespace std;
using namespace Ice;
using namespace IcePatch;

string
normalizePath(const string& path)
{
    string result = path;
    
    string::size_type pos;
    
    for(pos = 0; pos < result.size(); ++pos)
    {
	if(result[pos] == '\\')
	{
	    result[pos] = '/';
	}
    }
    
    pos = 0;
    while((pos = result.find("//", pos)) != string::npos)
    {
	result.erase(pos, 1);
    }
    
    pos = 0;
    while((pos = result.find("/./", pos)) != string::npos)
    {
	result.erase(pos, 2);
    }

    if(result.substr(0, 2) == "./")
    {
        result.erase(0, 2);
    }

    if(result.size() >= 2 && result.substr(result.size() - 2, 2) == "/.")
    {
        result.erase(result.size() - 2, 2);
    }

    return result;
}

string
IcePatch::identityToPath(const Identity& ident)
{
    assert(ident.category == "IcePatch");
    return normalizePath(ident.name);
}

Identity
IcePatch::pathToIdentity(const string& path)
{
    Identity ident;
    ident.category = "IcePatch";
    ident.name = normalizePath(path);
    return ident;
}

string
IcePatch::getSuffix(const string& path)
{
    string::size_type pos = path.rfind('.');
    if(pos == string::npos)
    {
	return string();
    }
    else
    {
	return path.substr(pos + 1);
    }
}

bool
IcePatch::ignoreSuffix(const string& path)
{
    string suffix = getSuffix(path);
    return suffix == "md5" || suffix == "md5temp" || suffix == "bz2" || suffix == "bz2temp";
}

string
IcePatch::removeSuffix(const string& path)
{
    string::size_type pos = path.rfind('.');
    if(pos == string::npos)
    {
	return path;
    }
    else
    {
	return path.substr(0, pos);
    }
}

FileInfo
IcePatch::getFileInfo(const string& path, bool exceptionIfNotExist)
{
    struct stat buf;
    if(::stat(path.c_str(), &buf) == -1)
    {
	if(!exceptionIfNotExist && errno == ENOENT)
	{
	    FileInfo result;
	    result.size = 0;
	    result.time = 0;
	    result.type = FileTypeNotExist;
            return result;
	}
	else
	{
	    FileAccessException ex;
	    ex.reason = "cannot stat `" + path + "': " + strerror(errno);
	    throw ex;
	}
    }

    FileInfo result;
    result.size = buf.st_size;
    result.time = buf.st_mtime;

    if(S_ISDIR(buf.st_mode))
    {
	result.type = FileTypeDirectory;
    }
    else if(S_ISREG(buf.st_mode))
    {
	result.type = FileTypeRegular;
    }
    else
    {
	result.type = FileTypeUnknown;
    }
    
    return result;
}

void
IcePatch::removeRecursive(const string& path)
{
    if(getFileInfo(path, true).type == FileTypeDirectory)
    {
	StringSeq paths = readDirectory(path);
        for(StringSeq::const_iterator p = paths.begin(); p != paths.end(); ++p)
	{
	    removeRecursive(*p);
	}
    }
    
    if(::remove(path.c_str()) == -1)
    {
	FileAccessException ex;
	ex.reason = "cannot remove file `" + path + "': " + strerror(errno);
	throw ex;
    }
}

StringSeq
IcePatch::readDirectory(const string& path)
{
#ifdef _WIN32

    struct _finddata_t data;
    long h = _findfirst((path + "/*").c_str(), &data);
    if(h == -1)
    {
	FileAccessException ex;
	ex.reason = "cannot read directory `" + path + "': " + strerror(errno);
	throw ex;
    }
    
    StringSeq result;

    while(true)
    {
	string name = data.name;
	assert(!name.empty());

	if(name != ".." && name != ".")
	{
	    result.push_back(normalizePath(path + '/' + name));
	}

        if(_findnext(h, &data) == -1)
        {
            if(errno == ENOENT)
            {
                break;
            }

            FileAccessException ex;
            ex.reason = "cannot read directory `" + path + "': " + strerror(errno);
            _findclose(h);
            throw ex;
        }
    }

    _findclose(h);

    sort(result.begin(), result.end());

    return result;

#else

    struct dirent **namelist;
    int n = ::scandir(path.c_str(), &namelist, 0, alphasort);
    if(n < 0)
    {
	FileAccessException ex;
	ex.reason = "cannot read directory `" + path + "': " + strerror(errno);
	throw ex;
    }

    StringSeq result;
    result.reserve(n - 2);

    for(int i = 0; i < n; ++i)
    {
	string name = namelist[i]->d_name;
	assert(!name.empty());

	free(namelist[i]);

	if(name != ".." && name != ".")
	{
	    result.push_back(normalizePath(path + '/' + name));
	}
    }
    
    free(namelist);
    return result;

#endif
}

void
IcePatch::createDirectory(const string& path)
{
#ifdef _WIN32
    if(::_mkdir(path.c_str()) == -1)
#else
    if(::mkdir(path.c_str(), 00777) == -1)
#endif
    {
	FileAccessException ex;
	ex.reason = "cannot create directory `" + path + "': " + strerror(errno);
	throw ex;
    }
}

ByteSeq
IcePatch::getMD5(const string& path)
{
    string pathMD5 = path + ".md5";
    ifstream fileMD5(pathMD5.c_str(), ios::binary);
    if(!fileMD5)
    {
	FileAccessException ex;
	ex.reason = "cannot open `" + pathMD5 + "' for reading: " + strerror(errno);
	throw ex;
    }
    ByteSeq bytesMD5;
    bytesMD5.resize(16);
    fileMD5.read(&bytesMD5[0], 16);
    if(!fileMD5)
    {
	FileAccessException ex;
	ex.reason = "cannot read `" + pathMD5 + "': " + strerror(errno);
	throw ex;
    }
    if(fileMD5.gcount() < 16)
    {
	FileAccessException ex;
	ex.reason = "could not read 16 bytes from `" + pathMD5 + "'";
	throw ex;
    }
    fileMD5.close();
    return bytesMD5;
}

ByteSeq
IcePatch::getPartialMD5(const string& path, Int size)
{
    if(size < 0)
    {
	FileAccessException ex;
	ex.reason = "negative file size is illegal";
	throw ex;
    }
    
    //
    // Read the original file partially.
    //
    FileInfo info = getFileInfo(path, true);
    size = std::min(size, static_cast<Int>(info.size));
    ifstream file(path.c_str(), ios::binary);
    if(!file)
    {
	FileAccessException ex;
	ex.reason = "cannot open `" + path + "' for reading: " + strerror(errno);
	throw ex;
    }
    ByteSeq bytes;
    bytes.resize(size);
    file.read(&bytes[0], bytes.size());
    if(!file)
    {
	FileAccessException ex;
	ex.reason = "cannot read `" + path + "': " + strerror(errno);
	throw ex;
    }
    if(file.gcount() < static_cast<int>(bytes.size()))
    {
	FileAccessException ex;
	ex.reason = "could not read all bytes from `" + path + "'";
	throw ex;
    }
    file.close();
    
    //
    // Create the MD5 hash value.
    //
    ByteSeq bytesMD5;
    bytesMD5.resize(16);
    MD5(reinterpret_cast<unsigned char*>(&bytes[0]), bytes.size(), reinterpret_cast<unsigned char*>(&bytesMD5[0]));

    return bytesMD5;
}

void
IcePatch::createMD5(const string& path)
{
    FileInfo info = getFileInfo(path, true);
    if(info.type == FileTypeUnknown)
    {
	FileAccessException ex;
	ex.reason = "cannot create .md5 file for `" + path + "' because file type is unknown";
	throw ex;
    }

    string pathMD5;
    string pathMD5Temp;
    ByteSeq bytes;
    if(info.type == FileTypeDirectory)
    {
	pathMD5 = path + "/.md5";
	pathMD5Temp = path + "/.md5temp";
	
	//
	// Read all MD5 files in the directory.
	//
	StringSeq paths = readDirectory(path);
	for(StringSeq::const_iterator p = paths.begin(); p != paths.end(); ++p)
	{
	    if(!ignoreSuffix(*p))
	    {
		FileInfo subInfo = getFileInfo(*p, true);
		
		if(subInfo.type == FileTypeDirectory)
		{
		    ByteSeq subBytesMD5 = getMD5(*p + "/.md5");
		    copy(subBytesMD5.begin(), subBytesMD5.end(), back_inserter(bytes));
		}
		else if(subInfo.type == FileTypeRegular)
		{
		    ByteSeq subBytesMD5 = getMD5(removeSuffix(*p));
		    copy(subBytesMD5.begin(), subBytesMD5.end(), back_inserter(bytes));
		}
	    }
	}
    }
    else
    {
	assert(info.type == FileTypeRegular);

	pathMD5 = path + ".md5";
	pathMD5Temp = path + ".md5temp";

	//
	// Read the original file.
	//
	ifstream file(path.c_str(), ios::binary);
	if(!file)
	{
	    FileAccessException ex;
	    ex.reason = "cannot open `" + path + "' for reading: " + strerror(errno);
	    throw ex;
	}
	bytes.resize(info.size);
	file.read(&bytes[0], bytes.size());
	if(!file)
	{
	    FileAccessException ex;
	    ex.reason = "cannot read `" + path + "': " + strerror(errno);
	    throw ex;
	}
	if(file.gcount() < static_cast<int>(bytes.size()))
	{
	    FileAccessException ex;
	    ex.reason = "could not read all bytes from `" + path + "'";
	    throw ex;
	}
	file.close();
    }
    
    //
    // Create the MD5 hash value.
    //
    ByteSeq bytesMD5;
    bytesMD5.resize(16);
    MD5(reinterpret_cast<unsigned char*>(&bytes[0]), bytes.size(), reinterpret_cast<unsigned char*>(&bytesMD5[0]));
    
    //
    // Save the MD5 hash value to a temporary MD5 file.
    //
    ofstream fileMD5(pathMD5Temp.c_str(), ios::binary);
    if(!fileMD5)
    {
	FileAccessException ex;
	ex.reason = "cannot open `" + pathMD5Temp + "' for writing: " + strerror(errno);
	throw ex;
    }
    fileMD5.write(&bytesMD5[0], 16);
    if(!fileMD5)
    {
	FileAccessException ex;
	ex.reason = "cannot write `" + pathMD5Temp + "': " + strerror(errno);
	throw ex;
    }
    fileMD5.close();
    
    //
    // Rename the temporary MD5 file to the final MD5 file. This is
    // done so that there can be no partial MD5 files after an
    // abortive application termination.
    //
    ::remove(pathMD5.c_str());
    if(::rename(pathMD5Temp.c_str(), pathMD5.c_str()) == -1)
    {
	FileAccessException ex;
	ex.reason = "cannot rename `" + pathMD5Temp + "' to  `" + pathMD5 + "': " + strerror(errno);
	throw ex;
    }
}

ByteSeq
IcePatch::getBZ2(const string& path, Int pos, Int num)
{
    if(pos < 0)
    {
	FileAccessException ex;
	ex.reason = "negative read offset is illegal";
	throw ex;
    }

    if(num < 0)
    {
	FileAccessException ex;
	ex.reason = "negative data segment size is illegal";
	throw ex;
    }

    if(num > 1024 * 1024)
    {
	FileAccessException ex;
	ex.reason = "maxium data segment size exceeded";
	throw ex;
    }
    
    string pathBZ2 = path + ".bz2";
    ifstream fileBZ2(pathBZ2.c_str(), ios::binary);
    if(!fileBZ2)
    {
	FileAccessException ex;
	ex.reason = "cannot open `" + pathBZ2 + "' for reading: " + strerror(errno);
	throw ex;
    }
    fileBZ2.seekg(pos);
    if(!fileBZ2)
    {
	FileAccessException ex;
	ostringstream out;
	out << "cannot seek position " << pos << " in file `" << path << "':" << strerror(errno);
	ex.reason = out.str();
	throw ex;
    }
    ByteSeq bytesBZ2;
    bytesBZ2.resize(num);
    fileBZ2.read(&bytesBZ2[0], bytesBZ2.size());
    if(!fileBZ2 && !fileBZ2.eof())
    {
	FileAccessException ex;
	ex.reason = "cannot read `" + pathBZ2 + "': " + strerror(errno);
	throw ex;
    }
    bytesBZ2.resize(fileBZ2.gcount());
    fileBZ2.close();
    return bytesBZ2;
}

void
IcePatch::createBZ2(const string& path)
{
    FileInfo info = getFileInfo(path, true);
    if(info.type == FileTypeUnknown)
    {
	FileAccessException ex;
	ex.reason = "cannot create .bz2 file for `" + path + "' because file type is unknown";
	throw ex;
    }
    if(info.type == FileTypeDirectory)
    {
	FileAccessException ex;
	ex.reason = "cannot create .bz2 file for `" + path + "' because this is a directory";
	throw ex;
    }

    //
    // Read the original file in blocks and write a temporary BZ2
    // file.
    //
    ifstream file(path.c_str(), ios::binary);
    if(!file)
    {
	FileAccessException ex;
	ex.reason = "cannot open `" + path + "' for reading: " + strerror(errno);
	throw ex;
    }

    string pathBZ2 = path + ".bz2";
    string pathBZ2Temp = path + ".bz2temp";
    FILE* stdioFileBZ2 = fopen(pathBZ2Temp.c_str(), "wb");
    if(!stdioFileBZ2)
    {
	FileAccessException ex;
	ex.reason = "cannot open `" + pathBZ2Temp + "' for writing: " + strerror(errno);
	throw ex;
    }
    
    int bzError;
    BZFILE* bzFile = BZ2_bzWriteOpen(&bzError, stdioFileBZ2, 5, 0, 0);
    if(bzError != BZ_OK)
    {
	FileAccessException ex;
	ex.reason = "BZ2_bzWriteOpen failed";
	if(bzError == BZ_IO_ERROR)
	{
	    ex.reason += string(": ") + strerror(errno);
	}
	fclose(stdioFileBZ2);
	throw ex;
    }
    
    static const Int num = 64 * 1024;
    Byte bytes[num];
    
    while(!file.eof())
    {
	file.read(bytes, num);
	if(!file && !file.eof())
	{
	    FileAccessException ex;
	    ex.reason = "cannot read `" + path + "': " + strerror(errno);
	    BZ2_bzWriteClose(&bzError, bzFile, 0, 0, 0);
	    fclose(stdioFileBZ2);
	    throw ex;
	}
	
	if(file.gcount() > 0)
	{
	    BZ2_bzWrite(&bzError, bzFile, bytes, file.gcount());
	    if(bzError != BZ_OK)
	    {
		FileAccessException ex;
		ex.reason = "BZ2_bzWrite failed";
		if(bzError == BZ_IO_ERROR)
		{
		    ex.reason += string(": ") + strerror(errno);
		}
		BZ2_bzWriteClose(&bzError, bzFile, 0, 0, 0);
		fclose(stdioFileBZ2);
		throw ex;
	    }
	}
    }
    
    BZ2_bzWriteClose(&bzError, bzFile, 0, 0, 0);
    if(bzError != BZ_OK)
    {
	FileAccessException ex;
	ex.reason = "BZ2_bzWriteClose failed";
	if(bzError == BZ_IO_ERROR)
	{
	    ex.reason += string(": ") + strerror(errno);
	}
	fclose(stdioFileBZ2);
	throw ex;
    }
    
    fclose(stdioFileBZ2);
    file.close();
    
    //
    // Rename the temporary BZ2 file to the final BZ2 file. This is
    // done so that there can be no partial BZ2 files after an
    // abortive application termination.
    //
    ::remove(pathBZ2.c_str());
    if(::rename(pathBZ2Temp.c_str(), pathBZ2.c_str()) == -1)
    {
	FileAccessException ex;
	ex.reason = "cannot rename `" + pathBZ2Temp + "' to  `" + pathBZ2 + "': " + strerror(errno);
	throw ex;
    }
}

void
IcePatch::getRegular(const RegularPrx& regular, ProgressCB& progressCB)
{
    string path = identityToPath(regular->ice_getIdentity());
    string pathBZ2 = path + ".bz2";
    Int totalBZ2 = regular->getBZ2Size();
    Int posBZ2 = 0;

    //
    // Check for partial BZ2 file.
    //
    FileInfo infoBZ2 = getFileInfo(pathBZ2, false);
    if(infoBZ2.type == FileTypeRegular)
    {
	ByteSeq remoteBZ2MD5 = regular->getBZ2MD5(infoBZ2.size);
	ByteSeq localBZ2MD5 = getPartialMD5(pathBZ2, infoBZ2.size);

	if(remoteBZ2MD5 == localBZ2MD5)
	{
	    posBZ2 = infoBZ2.size;
	}
    }

    //
    // Get the BZ2 file.
    //
    progressCB.startDownload(totalBZ2, posBZ2);

    ofstream fileBZ2(pathBZ2.c_str(), ios::binary | (posBZ2 ? ios::app : 0));
    if(!fileBZ2)
    {
	FileAccessException ex;
	ex.reason = "cannot open `" + pathBZ2 + "' for writing: " + strerror(errno);
	throw ex;
    }

    while(posBZ2 < totalBZ2)
    {
	static const Int numBZ2 = 64 * 1024;

	ByteSeq bytesBZ2 = regular->getBZ2(posBZ2, numBZ2);
	if(bytesBZ2.empty())
	{
	    break;
	}
	
	posBZ2 += bytesBZ2.size();
	
	fileBZ2.write(&bytesBZ2[0], bytesBZ2.size());
	if(!fileBZ2)
	{
	    FileAccessException ex;
	    ex.reason = "cannot write `" + pathBZ2 + "': " + strerror(errno);
	    throw ex;
	}
	
	if(static_cast<Int>(bytesBZ2.size()) < numBZ2)
	{
	    break;
	}
	
	progressCB.updateDownload(totalBZ2, posBZ2);
    }

    progressCB.finishedDownload(totalBZ2);

    fileBZ2.close();
    
    //
    // Read the BZ2 file in blocks and write the original file.
    //
    ofstream file(path.c_str(), ios::binary);
    if(!file)
    {
	FileAccessException ex;
	ex.reason = "cannot open `" + path + "' for writing: " + strerror(errno);
	throw ex;
    }
    
    FILE* stdioFileBZ2 = fopen(pathBZ2.c_str(), "rb");
    if(!stdioFileBZ2)
    {
	FileAccessException ex;
	ex.reason = "cannot open `" + pathBZ2 + "' for reading: " + strerror(errno);
	throw ex;
    }
    
    int bzError;
    BZFILE* bzFile = BZ2_bzReadOpen(&bzError, stdioFileBZ2, 0, 0, 0, 0);
    if(bzError != BZ_OK)
    {
	FileAccessException ex;
	ex.reason = "BZ2_bzReadOpen failed";
	if(bzError == BZ_IO_ERROR)
	{
	    ex.reason += string(": ") + strerror(errno);
	}
	fclose(stdioFileBZ2);
	throw ex;
    }
    
    static const Int numBZ2 = 64 * 1024;
    Byte bytesBZ2[numBZ2];
    
    progressCB.startUncompress(totalBZ2, 0);
    
    while(bzError != BZ_STREAM_END)
    {
	int sz = BZ2_bzRead(&bzError, bzFile, bytesBZ2, numBZ2);
	if(bzError != BZ_OK && bzError != BZ_STREAM_END)
	{
	    FileAccessException ex;
	    ex.reason = "BZ2_bzRead failed";
	    if(bzError == BZ_IO_ERROR)
	    {
		ex.reason += string(": ") + strerror(errno);
	    }
	    BZ2_bzReadClose(&bzError, bzFile);
	    fclose(stdioFileBZ2);
	    throw ex;
	}
	
	if(sz > 0)
	{
	    long pos = ftell(stdioFileBZ2);
	    if(pos == -1)
	    {
		FileAccessException ex;
		ex.reason = "cannot get read position for `" + pathBZ2 + "': " + strerror(errno);
		BZ2_bzReadClose(&bzError, bzFile);
		fclose(stdioFileBZ2);
		throw ex;
	    }

	    progressCB.updateUncompress(totalBZ2, pos);
	    
	    file.write(bytesBZ2, sz);
	    if(!file)
	    {
		FileAccessException ex;
		ex.reason = "cannot write `" + path + "': " + strerror(errno);
		BZ2_bzReadClose(&bzError, bzFile);
		fclose(stdioFileBZ2);
		throw ex;
	    }
	}
    }
    
    progressCB.finishedUncompress(totalBZ2);
    
    BZ2_bzReadClose(&bzError, bzFile);
    if(bzError != BZ_OK)
    {
	FileAccessException ex;
	ex.reason = "BZ2_bzReadClose failed";
	if(bzError == BZ_IO_ERROR)
	{
	    ex.reason += string(": ") + strerror(errno);
	}
	fclose(stdioFileBZ2);
	throw ex;
    }

    fclose(stdioFileBZ2);
    file.close();
    
    //
    // Remove the BZ2 file, it is not needed anymore.
    //
    if(::remove(pathBZ2.c_str()) == -1)
    {
	FileAccessException ex;
	ex.reason = "cannot remove file `" + pathBZ2 + "': " + strerror(errno);
	throw ex;
    }

    //
    // Create a MD5 file for the original file.
    //
    createMD5(path);
}
