#!/usr/bin/env python
# **********************************************************************
#
# Copyright (c) 2003-2007 ZeroC, Inc. All rights reserved.
#
# This copy of Ice is licensed to you under the terms described in the
# ICE_LICENSE file included in this distribution.
#
# **********************************************************************

#
# TestUtil global flags section! 
#
# You can modify the following variables to control which tests are run
# by default. Command line options provided at runtime will override
# these values.
#
protocol = ""                   # If unset, default to TCP. Valid values are "tcp" or "ssl".
compress = 0                    # Set to 1 to enable bzip2 compression.
threadPerConnection = 0         # Set to 1 to have tests use thread per connection concurrency model.
host = "127.0.0.1"              # Default to loopback.
debug = 0                       # Set to 1 to enable test suite debugging.
mono =  0                       # Set to 1 to use Mono as the default .NET CLR.
keepGoing = 0                   # Set to 1 to have the tests continue on failure.

javaCmd = "java"                # Default java loader
phpCmd = "php"                  # Name of default php binary (usually php or php5)

################################################################################
#
# End of global flags section. Do not edit beyond this point.
#
################################################################################

#
# This is set by the choice of init method. If not set, before it is
# used, it indicates a bug and things should terminate.
#
defaultMapping = None

testErrors = []

import sys, os, re, errno, getopt, time, StringIO
from threading import Thread

usageMessage = "usage: " + sys.argv[0] + """
  --all                   Run all permutations of the tests."
  --start=<regex>         Start running the tests at the given test."
  --start-after=<regex>   Start running the tests after the given test.
  --loop                  Run the tests in a loop.
  --filter=<regex>        Run all the tests that match the given regex.
  --rfilter=<regex>       Run all the tests that do not match the given regex.
  --debug                 Display debugging information on each test.
  --protocol=tcp|ssl      Run with the given protocol.
  --compress              Run the tests with protocol compression.
  --host=host             Set --Ice.Default.Host=<host>.
  --threadPerConnection   Run with thread-per-connection concurrency model.
  --continue              Keep running when a test fails
"""

def configurePaths():
    toplevel = findTopLevel()

    if isWin32():
        os.environ["PATH"] = os.path.join(toplevel, "cpp", "bin") + os.pathsep + os.getenv("PATH", "")
    elif isHpUx():
        os.environ["SHLIB_PATH"] = os.path.join(toplevel, "cpp", "lib") + os.pathsep + os.getenv("SHLIB_PATH", "")
    elif isDarwin():
        os.environ["DYLD_LIBRARY_PATH"] = os.path.join(toplevel, "cpp", "lib") + os.pathsep + os.getenv("DYLD_LIBRARY_PATH", "")
        os.environ["DYLD_BIND_AT_LAUNCH"] = "1"
    elif isAIX():
        os.environ["LIBPATH"] = os.path.join(toplevel, "cpp", "lib") + os.pathsep + os.getenv("LIBPATH", "")
    else:
        os.environ["LD_LIBRARY_PATH"] = os.path.join(toplevel, "cpp", "lib") + os.pathsep + os.getenv("LD_LIBRARY_PATH", "")
        os.environ["LD_LIBRARY_PATH_64"] = os.path.join(toplevel, "cpp", "lib") + os.pathsep + os.getenv("LD_LIBRARY_PATH_64", "")

    os.environ["CLASSPATH"] = os.path.join(toplevel, "java", "lib", "Ice.jar") + os.pathsep + os.getenv("CLASSPATH", "")
    os.environ["CLASSPATH"] = os.path.join(toplevel, "java", "lib") + os.pathsep + os.getenv("CLASSPATH", "")

def addLdPath(libpath):
    if isWin32():
        os.environ["PATH"] = libpath + os.pathsep + os.getenv("PATH", "")
    elif isHpUx():
        os.environ["SHLIB_PATH"] = libpath + os.pathsep + os.getenv("SHLIB_PATH", "")
    elif isDarwin():
        os.environ["DYLD_LIBRARY_PATH"] = libpath + os.pathsep + os.getenv("DYLD_LIBRARY_PATH", "")
    elif isAIX():
        os.environ["LIBPATH"] = libpath + os.pathsep + os.getenv("LIBPATH", "")
    else:
        os.environ["LD_LIBRARY_PATH"] = libpath + os.pathsep + os.getenv("LD_LIBRARY_PATH", "")
        os.environ["LD_LIBRARY_PATH_64"] = libpath + os.pathsep + os.getenv("LD_LIBRARY_PATH_64", "")
    
def isCygwin():
    # The substring on sys.platform is required because some cygwin
    # versions return variations like "cygwin_nt-4.01".
    return sys.platform[:6] == "cygwin"

def isWin32():
    return sys.platform == "win32" or isCygwin()

def isVista():
    return isWin32() and sys.getwindowsversion()[0] == 6

def isWin9x():
    if isWin32():
        return not (os.environ.has_key("OS") and os.environ["OS"] == "Windows_NT")
    else:
        return 0

def isSolaris():
    return sys.platform == "sunos5"
       
def isHpUx():
   return sys.platform == "hp-ux11"

def isAIX():
   return sys.platform in ['aix4', 'aix5']
  
def isDarwin():
   return sys.platform == "darwin"

def usage():
    global usageMessage
    print usageMessage
    sys.exit(2)

def index(l, re):
    """Find the index of the first item in the list that matches the given re"""
    for i in range(0, len(l)):
        if re.search(l[i]):
            return i
    return -1

def getTestSet(tests):
    resultSet = tests[start:] 
    if testFilter != None:
        if removeFilter:
            resultSet = [ x for x in tests if not testFilter.search(x) ]
        else:
            resultSet = [ x for x in tests if testFilter.search(x) ]
    return resultSet

def run(tests):
    global arg
    testset = getTestSet(tests)
    args =  []
    if all:
        for protocol in ["ssl", "tcp"]:
            for compress in [0, 1]:
                for threadPerConnection in [0, 1]:
                    testarg = ""
                    if compress:
                        testarg += "--compress"
                    if threadPerConnection:
                        testarg += " --threadPerConnection"
                    testarg += " --protocol %s" % (protocol)
                    args.append(testarg)
    else:
        args.append(arg)

    if loop:
        num = 1
        while 1:
            for arg in args:
                runTests(arg, [ os.path.join(getDefaultMapping(), "test", x) for x in testset ], num)
            num += 1
    else:
        for arg in args:
            runTests(arg, [ os.path.join(getDefaultMapping(), "test", x) for x in testset ])

    global testErrors
    if len(testErrors) > 0:
        print "The following errors occurred:"
        for x in testErrors:
            print x

def rootRun(tests):
    global arg
    if loop:
        print "Looping is currently disabled for running all tests from the root!"
    else:
        if all:
            for protocol in ["ssl", "tcp"]:
                for compress in [0, 1]:
                    for threadPerConnection in [0, 1]:
                        testarg = ""
                        if compress:
                            testarg += "--compress"
                        if threadPerConnection:
                            testarg += " --threadPerConnection"
                        testarg += " --protocol %s" % (protocol)
                        args.append(testarg)
        else:
            args.append(arg)

        for arg in args:
            runTests(arg, tests)

    global testErrors
    if len(testErrors) > 0:
        print "The following errors occurred:"
        for x in testErrors:
            print x

if not isWin32():
    mono = 1
    
toplevel = None 

def findTopLevel():
    global toplevel

    if toplevel != None:
        return toplevel

    for toplevel in [".", "..", "../..", "../../..", "../../../..", "../../../../.."]:
        toplevel = os.path.abspath(toplevel)
        if os.path.exists(os.path.join(toplevel, "config", "TestUtil.py")):
            break
    else:
        toplevel = None
        raise "can't find toplevel directory!"

    return toplevel

findTopLevel()
configurePaths()
serverPids = []
serverThreads = []
allServerThreads = []

phpExtensionDir = None
phpExtension = None

if isWin32():
    phpExtensionDir = os.path.abspath(os.path.join(findTopLevel(), "php", "bin"))
    phpExtension = "php_ice.dll"
    #
    # TODO: When we no longer support PHP 5.1.x, we can do the following:
    #
    #phpCmd = "php -d extension_dir=\"" + os.path.abspath(os.path.join(toplevel, "bin")) + "\" -d extension=php_ice.dll"
else:
    if not isDarwin():
        cwd = os.getcwd()
        os.chdir(os.environ["HOME"])
        os.chdir(cwd)
        p = os.popen("php -v 2>/dev/null")
        l = p.readlines()
        if p.close() != None:
            phpCmd = "php5"

    phpExtensionDir = os.path.abspath(os.path.join(findTopLevel(), "php", "lib"))
    phpExtension = "IcePHP.so"
    #
    # TODO: When we no longer support PHP 5.1.x, we can do the following:
    #
    #phpCmd = "php -d extension_dir=\"" + os.path.abspath(os.path.join(toplevel, "lib")) + "\" -d extension=IcePHP.so"

def getIceSoVersion():

    config = open(os.path.join(findTopLevel(), "cpp", "include", "IceUtil", "Config.h"), "r")
    intVersion = int(re.search("ICE_INT_VERSION ([0-9]*)", config.read()).group(1))
    majorVersion = intVersion / 10000
    minorVersion = intVersion / 100 - 100 * majorVersion    
    patchVersion = intVersion % 100
    if patchVersion > 50:
        if patchVersion >= 52:
            return '%db%d' % (majorVersion * 10 + minorVersion, patchVersion - 50)
        else:
            return '%db' % (majorVersion * 10 + minorVersion)
    else:
        return '%d' % (majorVersion * 10 + minorVersion)

def getIceSSLVersion():
    javaPipeIn, javaPipeOut = os.popen4("java IceSSL.Util")
    if not javaPipeIn or not javaPipeOut:
        print "unable to get IceSSL version!"
        sys.exit(1)
    version = javaPipeOut.readline()
    if not version:
        print "unable to get IceSSL version!"
        sys.exit(1)
    javaPipeIn.close()
    javaPipeOut.close()
    return version.strip()

def getJdkVersion():
    javaPipeIn, javaPipeOut = os.popen4("java -version")
    if not javaPipeIn or not javaPipeOut:
        print "unable to get Java version!"
        sys.exit(1)
    version = javaPipeOut.readline()
    if not version:
        print "unable to get Java version!"
        sys.exit(1)
    javaPipeIn.close()
    javaPipeOut.close()
    return version

def closePipe(pipe):
    try:
        status = pipe.close()
    except IOError, ex:
        # TODO: There's a waitpid problem on CentOS, so we have to ignore ECHILD.
        if ex.errno == errno.ECHILD:
            status = 0
        # This happens with the test/IceGrid/simple test on AIX, and the
        # C# fault tolerance test.
        elif ex.errno == 0:
            status = 0
        else:
            raise
    return status
     
class ReaderThread(Thread):
    def __init__(self, pipe):
        self.pipe = pipe
        Thread.__init__(self)

    def run(self):

        try:
            while 1:
                line = self.pipe.readline()
                if not line: break
                # Suppress "adapter ready" messages. Under windows the eol isn't \n.
                if not line.endswith(" ready\n") and not line.endswith(" ready\r\n"):
                    sys.stdout.flush()
                    print line,
        except IOError:
            pass

        self.status = closePipe(self.pipe)

    def getPipe(self):
        return self.pipe

    def getStatus(self):
        return self.status

def joinServers():
    global serverThreads
    global allServerThreads
    for t in serverThreads:
        t.join()
        allServerThreads.append(t)
    serverThreads = []

# This joins with all servers and if any of them failed then
# it returns the failure status.
def serverStatus():
    global allServerThreads
    joinServers()
    for t in allServerThreads:
        status = t.getStatus()
        if status:
            print "server ", str(t), " status: ", str(status)
            return status
    return 0

# This joins with a specific server (the one started with the given pipe)
# returns its exit status. If the server cannot be found an exception
# is raised.
def specificServerStatus(pipe, timeout = None):
    global serverThreads
    for t in serverThreads:
        if t.getPipe() == pipe:
            serverThreads.remove(t)
	    if isWin32() and timeout != None:
 		#
	        # BUGFIX: On Windows x64 with python 2.5 join with
	        # a timeout doesn't work (it hangs for the duration
		# of the timeout if the thread is alive at the time
		# of the join call).
		#
	        while timeout >= 0 and t.isAlive():
		    time.sleep(1)
   	   	    timeout -= 1
		if not t.isAlive():
		    t.join()
            else:
	        t.join(timeout)
            if t.isAlive():
                raise "server with pipe " + str(pipe) + " did not exit within the timeout period."
            status = t.getStatus()
            return status
    raise "can't find server with pipe: " + str(pipe)

def killServers():
    global serverPids
    global serverThreads

    for pid in serverPids:

        if isWin32():
            try:
                import win32api
                handle = win32api.OpenProcess(1, 0, pid)
                win32api.TerminateProcess(handle, 0)
            except ImportError, ex:
                print "Sorry: you must install the win32all package for killServers to work."
                return
            except:
                pass # Ignore errors, such as non-existing processes.
        else:
            try:
                os.kill(pid, 9)
            except:
                pass # Ignore errors, such as non-existing processes.

    serverPids = []

    #
    # Now join with all the threads
    #
    joinServers()

def getServerPid(pipe):
    global serverPids
    global serverThreads

    output = ignorePid(pipe)

    try:
        serverPids.append(int(output))
    except ValueError:
        print "Output is not a PID: " + output
        raise

def ignorePid(pipe):
    while 1:
        output = pipe.readline().strip()
        if not output:
            print "failed!"
            killServers()
            sys.exit(1)
        if output.startswith("warning: "):
            continue
        return output

def getAdapterReady(pipe, createThread = True, count = 1):
    global serverThreads

    while count > 0: 
        output = pipe.readline().strip()
        count = count - 1

    if not output:
        print "failed!"
        killServers()
        sys.exit(1)

    # Start a thread for this server.
    if createThread:
        serverThread = ReaderThread(pipe)
        serverThread.start()
        serverThreads.append(serverThread)

def getIceBox(testdir):

    #
    # Get and return the path of the IceBox executable
    #

    iceBox = ""
    if isWin32():
        #
        # Read the build.txt file from the test directory to figure out 
        # how the IceBox service was built ("debug" vs. "release") and 
        # decide which icebox executable to use.
        # 
        build = open(os.path.join(testdir, "build.txt"), "r")
        type = build.read().strip()
        if type == "debug":
            iceBox = os.path.join(getBinDir(testdir), "iceboxd.exe")
        elif type == "release":
            iceBox = os.path.join(getBinDir(testdir), "icebox.exe")
    else:
        iceBox = os.path.join(getBinDir(testdir), "icebox")

    if iceBox == "" or not os.path.exists(iceBox):
        print "couldn't find icebox executable to run the test"
        sys.exit(0)

    return iceBox;

def waitServiceReady(pipe, token, createThread = True):
    global serverThreads

    while 1:
        output = pipe.readline().strip()
        if not output:
            print "failed!"
            sys.exit(1)
        if output == token + " ready":
            break

    # Start a thread for this server.
    if createThread:
        serverThread = ReaderThread(pipe)
        serverThread.start()
        serverThreads.append(serverThread)

def printOutputFromPipe(pipe):
    while 1:
        c = pipe.read(1)
        if c == "":
            break
        os.write(1, c)

def commonInit():
    configurePaths()

def javaInit():
    commonInit()

def cppInit():
    commonInit()

def pythonInit():
    commonInit()

def rubyInit():
    commonInit()

def dotnetInit():
    global usageMessage
    usageMessage = usageMessage + " -m|--mono"
   
    global validShortArgs
    validShortArgs = "m"

    global validLongArgs
    validLongArgs.append("mono")

    commonInit()

def phpInit():
    commonInit()

class InvalidSelectorString(Exception):
    def __init__(self, value):
        self.value = value
    def __str__(self):
        return repr(self.value)

sslConfigTree = { 
        "cpp" : { 
            "plugin" : " --Ice.Plugin.IceSSL=IceSSL:createIceSSL  --Ice.Default.Protocol=ssl --IceSSL.DefaultDir=%(certsdir)s " +  
            "--IceSSL.CertAuthFile=cacert.pem",
            "client" : " --IceSSL.CertFile=c_rsa1024_pub.pem --IceSSL.KeyFile=c_rsa1024_priv.pem",
            "server" : " --IceSSL.CertFile=s_rsa1024_pub.pem --IceSSL.KeyFile=s_rsa1024_priv.pem",
            "colloc" : " --IceSSL.CertFile=c_rsa1024_pub.pem --IceSSL.KeyFile=c_rsa1024_priv.pem"
            },
        "rb" : { 
            "plugin" : " --Ice.Plugin.IceSSL=IceSSL:createIceSSL  --Ice.Default.Protocol=ssl --IceSSL.DefaultDir=%(certsdir)s " +  
            "--IceSSL.CertAuthFile=cacert.pem",
            "client" : " --IceSSL.CertFile=c_rsa1024_pub.pem --IceSSL.KeyFile=c_rsa1024_priv.pem",
            "server" : " --IceSSL.CertFile=s_rsa1024_pub.pem --IceSSL.KeyFile=s_rsa1024_priv.pem",
            "colloc" : " --IceSSL.CertFile=c_rsa1024_pub.pem --IceSSL.KeyFile=c_rsa1024_priv.pem"
            },
        "java" : { 
            "plugin" : " --Ice.Plugin.IceSSL=IceSSL.PluginFactory --Ice.Default.Protocol=ssl --IceSSL.DefaultDir=%(certsdir)s " +  
            " --IceSSL.Truststore=certs.jks --IceSSL.Password=password",
            "client" : " --IceSSL.Keystore=client.jks",
            "server" : " --IceSSL.Keystore=server.jks",
            "colloc" : " --IceSSL.Keystore=client.jks"
            },
        "cs" : {
            "plugin" : " --Ice.Plugin.IceSSL=%(bindir)s\\icesslcs.dll:IceSSL.PluginFactory --Ice.Default.Protocol=ssl" +
            " --IceSSL.Password=password --IceSSL.DefaultDir=%(certsdir)s",
            "client" : " --IceSSL.CertFile=c_rsa1024.pfx --IceSSL.CheckCertName=0",
            "server" : " --IceSSL.CertFile=s_rsa1024.pfx --IceSSL.ImportCert.CurrentUser.Root=cacert.pem",
            "colloc" : " --IceSSL.CertFile=c_rsa1024.pfx --IceSSL.ImportCert.CurrentUser.Root=cacert.pem --IceSSL.CheckCertName=0"
            },
        }

def getDefaultMapping(currentDir = ""):
    """Try and guess the language mapping out of the current path"""

    if currentDir != "":
        # Caller has specified the current path to use as a base. 
        scriptPath = os.path.abspath(currentDir).split(os.sep)
        scriptPath.reverse()
        for p in scriptPath: 
            if p in ["cpp", "cs", "java", "php", "py", "rb", "tmp"]:
                return p

    scriptPath = os.path.abspath(sys.argv[0]).split(os.sep)
    scriptPath.reverse()
    for p in scriptPath: 
        if p in ["cpp", "cs", "java", "php", "py", "rb", "tmp"]:
            return p

    scriptPath = os.path.abspath(os.getcwd()).split(os.sep)
    scriptPath.reverse()
    for p in scriptPath: 
        if p in ["cpp", "cs", "java", "php", "py", "rb", "tmp"]:
            return p

    #  Default to C++
    return "cpp"

def getTestEnv():
    env = {}

    lang = getDefaultMapping()
    if lang == "cs":
        env["bindir"] = os.path.splitdrive(os.path.join(os.path.abspath(findTopLevel()), "cs", "bin"))[1]
        env["certsdir"] = os.path.splitdrive(os.path.join(os.path.abspath(findTopLevel()), "certs"))[1]
    else:
        env["certsdir"] = os.path.join(os.path.abspath(findTopLevel()), "certs")
        env["bindir"] = os.path.join(os.path.abspath(findTopLevel()), "cpp", "bin")
    return env 

class DriverConfig:
    lang = None
    protocol = None 
    compress = 0
    threadPerConnection = 0
    host = None 
    mono = False
    type = None
    overrides = None

    def __init__(self, type = None):
        global protocol
        global compress
        global threadPerConnection
        global host 
        global mono
        self.lang = getDefaultMapping()
        self.protocol = protocol
        self.compress = compress
        self.threadPerConnection = threadPerConnection
        self.host = host
        self.mono = mono
        self.type = type
        
def argsToDict(argumentString, results):
    """Converts an argument string to dictionary"""
    args = argumentString.strip()
    while len(args) > 0:
        end = args.find(" --")
        if end == -1:
            current = args.strip()
            args = ""
        else:
            current = args[:end].strip()
            args = args[end:].strip()

        value = current.find("=")
        if value != -1:
            results[current[:value]] = current[value+1:]
        else:
            results[current] = None
    return results
            
def getCommandLine(exe, config, env = getTestEnv()):
    #
    # Command lines are built up from the items in the components
    # sequence, which is initialized with command line options common to
    # all test drivers.
    #
    components = ["--Ice.NullHandleAbort", "--Ice.Warn.Connections"]

    #
    # Turn on network tracing.
    #
    # components.append("--Ice.Trace.Network=3")

    #
    # Now we add additional components dependent on the desired
    # configuration.
    #
    if config.protocol == "ssl":
        components.append(sslConfigTree[config.lang]["plugin"] % env)
        components.append(sslConfigTree[config.lang][config.type] % env)
    if config.compress:
        components.append("--Ice.Override.Compress")

    if config.threadPerConnection:
        components.append("--Ice.ThreadPerConnection")
    elif config.type == "server":
        components.append("--Ice.PrintProcessId --Ice.PrintAdapterReady --Ice.ServerIdleTime=30")
        if not (config.protocol == "ssl" and config.lang == "cs"):
            components.append("--Ice.ThreadPool.Server.Size=1 --Ice.ThreadPool.Server.SizeMax=3 --Ice.ThreadPool.Server.SizeWarn=0")

    if config.protocol == "ssl" and config.lang == "cs":
        components.append("--Ice.ThreadPerConnection=1")

    if config.host != None and len(config.host) != 0:
        components.append("--Ice.Default.Host=%s" % config.host)

    #
    # Not very many tests actually require an option override, so not to worried
    # about optimal here.
    #
    if config.overrides != None and len(config.overrides) > 0:
        propTable = {}
        for c in components:
            argsToDict(c, propTable)
                    
        argsToDict(config.overrides, propTable)
        components = []
        for k, v in propTable.iteritems():
            if v != None:
                components.append("%s=%s" % (k, v))
            else:
                components.append("%s" % k)
    
    output = StringIO.StringIO()
    if config.mono and config.lang == "cs":
        print >>output, "mono", "--debug %s.exe" % exe,
    elif config.lang == "rb" and config.type == "client":
        print >>output, "ruby", exe,
    elif config.lang == "java":
        print >>output, "%s -ea" % javaCmd, exe,
    elif config.lang == "py":
        print >>output, "python", exe,
    elif config.lang == "php" and config.type == "client":
        print >>output, phpCmd, "-c tmp.ini -f", exe, " -- ",
    else:
        print >>output, exe,

    for c in components:
        print >>output, c,
    commandline = output.getvalue()
    output.close()

    return commandline

def runTests(args, tests, num = 0):
    global testErrors
    global keepGoing

    #
    # Run each of the tests.
    #
    for i in tests:

        i = os.path.normpath(i)
        dir = os.path.join(toplevel, i)

        print
        if num > 0:
            print "[" + str(num) + "]",
        print "*** running tests in " + dir,
        print

        os.chdir(dir)

        if isWin9x():
            status = os.system("python " + os.path.join(dir, "run.py " + args))
        else:
            status = os.system(os.path.join(dir, "run.py " + args))

        if status:
            if(num > 0):
                print "[" + str(num) + "]",
            message = "test in " + os.path.abspath(dir) + " failed with exit status", status,
            print message
            if keepGoing == 0:
                sys.exit(status)
            else:
                print " ** Error logged and will be displayed again when suite is completed **"
                testErrors.append(message)

def getDefaultServerFile():
    lang = getDefaultMapping()
    if lang in ["rb", "php", "cpp", "cs"]:
        return "server"
    if lang == "py":
        return "Server.py"
    if lang == "java":
        return "Server"

def getDefaultClientFile():
    lang = getDefaultMapping()
    if lang == "rb":
        return "Client.rb"
    if lang == "php":
        return "Client.php"
    if lang in ["cpp", "cs"]:
        return "client"
    if lang == "py":
        return "Client.py"
    if lang == "java":
        return "Client"

def getDefaultCollocatedFile():
    lang = getDefaultMapping()
    if lang == "rb":
        return "Collocated.rb"
    if lang == "php":
        return "Collocated.php"
    if lang in ["cpp", "cs"]:
        return "collocated"
    if lang == "py":
        return "Collocated.py"
    if lang == "java":
        return "Collocated"

def clientServerTestWithOptionsAndNames(name, additionalServerOptions, additionalClientOptions, \
                                        serverName, clientName):
    lang = getDefaultMapping()
    testdir = os.path.join(findTopLevel(), lang, "test", name)
    
    server = serverName
    client = clientName
    
    if lang != "java":
        if lang in ["rb", "php"]:
            server = os.path.join(findTopLevel(), "cpp", "test", name, serverName)
        else:
            server = os.path.join(testdir, serverName)
        client = os.path.join(testdir, clientName)
    
    print "starting " + serverName + "...",
    serverCfg = DriverConfig("server")
    if lang in ["rb", "php"]:
        serverCfg.lang = "cpp"
    serverCmd = getCommandLine(server, serverCfg) + additionalServerOptions
    if debug:
        print "(" + serverCmd + ")",
    serverPipe = os.popen(serverCmd + " 2>&1")
    if lang != "java":
        getServerPid(serverPipe)
    getAdapterReady(serverPipe)
    print "ok"

    cwd = os.getcwd()
    os.chdir(testdir)

    if lang == "php":
        ini = open("php.ini", "r").readlines()
        for i in range(0, len(ini)):
            ini[i] = ini[i].replace("ICE_HOME", os.path.join(findTopLevel()))
        tmpini = open("tmp.ini", "w")
        tmpini.writelines(ini)
        tmpini.write("extension_dir=%s\n" % phpExtensionDir)
        tmpini.write("extension=%s\n" % phpExtension)
        tmpini.close()
        
    
    print "starting " + clientName + "...",
    clientCmd = getCommandLine(client, DriverConfig("client")) + additionalClientOptions
    if debug:
        print "(" + clientCmd + ")",
    clientPipe = os.popen(clientCmd + " 2>&1")
    print "ok"

    printOutputFromPipe(clientPipe)

    clientStatus = closePipe(clientPipe)
    if clientStatus:
        killServers()

    joinServers()
    os.chdir(cwd)

    if clientStatus or serverStatus():
        sys.exit(1)

def clientServerTestWithOptions(name, additionalServerOptions, additionalClientOptions):

    clientServerTestWithOptionsAndNames(name, additionalServerOptions, additionalClientOptions, getDefaultServerFile(),
                                        getDefaultClientFile())

def clientServerTest(name):

    clientServerTestWithOptions(name, "", "")

def clientServerTestWithClasspath(name, serverClasspath, clientClasspath):

    cp = os.getenv("CLASSPATH", "")
    scp = serverClasspath + os.pathsep + cp
    ccp = clientClasspath + os.pathsep + cp

    print "starting server...",
    os.environ["CLASSPATH"] = scp
    serverPipe = startServer(getDefaultServerFile(), "")
    os.environ["CLASSPATH"] = cp

    getAdapterReady(serverPipe)
    print "ok"

    print "starting client...",
    os.environ["CLASSPATH"] = ccp
    clientPipe = startClient(getDefaultClientFile(), "")
    os.environ["CLASSPATH"] = cp
    print "ok"

    printOutputFromPipe(clientPipe)
    clientStatus = closePipe(clientPipe)

    if clientStatus or serverStatus():
        killServers()
        sys.exit(1)

def mixedClientServerTestWithOptions(name, additionalServerOptions, additionalClientOptions):

    testdir = os.path.join(findTopLevel(), getDefaultMapping(), "test", name)
    lang = getDefaultMapping()
    server =  getDefaultServerFile()
    client = getDefaultClientFile()
    if lang != "java":
        server = os.path.join(testdir, server)
        client = os.path.join(testdir, client)

    print "starting server...",
    serverCmd = getCommandLine(server, DriverConfig("server")) + additionalServerOptions
    if debug:
        print "(" + serverCmd + ")",
    serverPipe = os.popen(serverCmd + " 2>&1")
    if lang != "java":
        getServerPid(serverPipe)
    getAdapterReady(serverPipe)
    print "ok"
    
    print "starting client...",
    clientCmd = getCommandLine(client, DriverConfig("client")) + additionalClientOptions
    if debug:
        print "(" + clientCmd + ")",
    clientPipe = os.popen(clientCmd + " 2>&1")
    ignorePid(clientPipe)
    getAdapterReady(clientPipe, False)
    print "ok"

    printOutputFromPipe(clientPipe)

    clientStatus = closePipe(clientPipe)

    if clientStatus:
        killServers()

    if clientStatus or serverStatus():
        sys.exit(1)

def mixedClientServerTest(name):

    mixedClientServerTestWithOptions(name, "", "")

def collocatedTestWithOptions(name, additionalOptions):

    testdir = os.path.join(findTopLevel(), getDefaultMapping(), "test", name)
    lang = getDefaultMapping()
    collocated = getDefaultCollocatedFile()
    if lang != "java":
        collocated = os.path.join(testdir, collocated) 

    print "starting collocated...",
    command = getCommandLine(collocated, DriverConfig("colloc")) + ' ' + additionalOptions 
    if debug:
        print "(" + command + ")",
    collocatedPipe = os.popen(command + " 2>&1")
    print "ok"

    printOutputFromPipe(collocatedPipe)

    collocatedStatus = closePipe(collocatedPipe)

    if collocatedStatus:
        sys.exit(1)

def collocatedTest(name):

    collocatedTestWithOptions(name, "")

def cleanDbDir(path):
    for filename in [ os.path.join(path, f) for f in os.listdir(path) if f != ".gitignore" and f != "DB_CONFIG" ]:
	os.remove(filename)

def startClient(exe, args, config=DriverConfig("client"), env=getTestEnv()):
    if debug:
        print getCommandLine(exe, config, env) + args

    if config.lang == "php":
        os.chdir(os.path.dirname(os.path.abspath(exe)))
        ini = open("php.ini", "r").readlines()
        for i in range(0, len(ini)):
            ini[i] = ini[i].replace("ICE_HOME", os.path.join(findTopLevel()))
        tmpini = open("tmp.ini", "w")
        tmpini.writelines(ini)
        tmpini.write("extension_dir=%s\n" % phpExtensionDir)
        tmpini.write("extension=%s\n" % phpExtension)
        tmpini.close()

    return os.popen(getCommandLine(exe, config, env) + args)

def startServer(exe, args, config=DriverConfig("server"), env=getTestEnv()):
    if debug:
        print getCommandLine(exe, config, env) + args
    return os.popen(getCommandLine(exe, config, env) + args)

def startColloc(exe, args, config=DriverConfig("colloc"), env=getTestEnv()):
    if debug:
        print getCommandLine(exe, config, env) + args
    return os.popen(getCommandLine(exe, config, env) + args)

def getMappingDir(currentDir):
    return os.path.abspath(os.path.join(findTopLevel(), getDefaultMapping(currentDir)))

def getBinDir(currentDir):
    return os.path.abspath(os.path.join(getMappingDir(currentDir), "bin"))

def getCertsDir(currentDir):
    return os.path.abspath(os.path.join(findTopLevel(), "certs"))

validShortArgs = "lr:R:"
validLongArgs = ["start=", "start-after=", "filter=", "rfilter=", "all", "loop", "debug", "protocol=",
                 "compress", "host=", "threadPerConnection", "continue"]

opts = []
args = []
loop = False
arg = ""
all = False

try:
    opts, args = getopt.getopt(sys.argv[1:], validShortArgs,  validLongArgs)
except getopt.GetoptError:
    usage()

if args:
    usage()

testFilter = None
removeFilter = False
start = 0

for o, a in opts:
    if o in ["-m", "--mono"]:
        mono = 1
    elif o == "--continue":
        keepGoing = 1
    elif o == "--compress":
        compress = 1
    elif o == "--threadPerConnection":
        threadPerConnection = 1
    elif o == "--host":
        host = a
    elif o in ("-l", "--loop"):
        loop = True
    elif o in ("-r", "-R", "--filter", '--rfilter'):
        testFilter = re.compile(a)
        if o in ("--rfilter", "-R"):
            removeFilter = True
    elif o == "--all" :
        all = True
    elif o in ( "--protocol", "--host", "--debug", "--compress", "--threadPerConnection" ):
        if o == "--protocol":
            if a not in ( "ssl", "tcp"):
                usage()
            protocol = a
        arg += " " + o

        if o == "--debug":
            debug = 1

        if len(a) > 0:
            arg += " " + a
    elif o in ('--start', "--start-after"):
        start = index(tests, re.compile(a))
        if start == -1:
            print "test %s not found. no tests to run" % (a)
            sys.exit(2)
        if o == "--start-after":
            start += 1
        tests = tests[start:]

if all and len(arg) > 0:
    usage()
