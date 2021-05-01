from conans import ConanFile
from conans import tools
from conans.tools import os_info, SystemPackageTool
import os, sys
import sysconfig
from io import StringIO

# From from *1 (see below, b2 --show-libraries), also ordered following linkage order
# see https://github.com/Kitware/CMake/blob/master/Modules/FindBoost.cmake to know the order
lib_list = ['math', 'wave', 'container', 'contract', 'exception', 'graph', 'iostreams', 'locale', 'log',
            'program_options', 'random', 'regex', 'mpi', 'serialization',
            'coroutine', 'fiber', 'context', 'timer', 'thread', 'chrono', 'date_time',
            'atomic', 'filesystem', 'system', 'graph_parallel', 'python',
            'stacktrace', 'test', 'type_erasure']

class BoostConan(ConanFile):
    name = "Boost"
    upstream_version = "1.75.0"
    package_revision = "-r1"
    version = "{0}{1}".format(upstream_version, package_revision)
    settings = "os", "arch", "compiler", "build_type"
    folder_name = "boost_%s" % upstream_version.replace(".", "_")
    # The current python option requires the package to be built locally, to find default Python
    # implementation
    options = {
        "shared": [True, False],
        "header_only": [True, False],
        "fPIC": [True, False],
        "skip_lib_rename": [True, False],
        "magic_autolink": [True, False], # enables BOOST_ALL_NO_LIB
        }
    options.update({"without_%s" % libname: [True, False] for libname in lib_list})

    default_options = ["shared=False",
        "header_only=False",
        "fPIC=False",
        "skip_lib_rename=True",
        "magic_autolink=False",
        ]
    default_options.extend(["without_%s=False" % libname for libname in lib_list if (libname != "python" or libname != "fiber")])
    default_options.append("without_python=True")
    default_options.append("without_fiber=True")
    default_options = tuple(default_options)

    url="https://github.com/ulricheck/conan-boost"
    # exports = ["FindBoost.cmake", "OriginalFindBoost*"]
    license="Boost Software License - Version 1.0. http://www.boost.org/LICENSE_1_0.txt"
    short_paths = True

    exports = ['patches/*']

    def config_options(self):
        """ First configuration step. Only settings are defined. Options can be removed
        according to these settings
        """
        if self.settings.compiler == "Visual Studio":
            self.options.remove("fPIC")

    @property
    def zip_bzip2_requires_needed(self):
        return not self.options.without_iostreams and not self.options.header_only

    def configure(self):
        """ Second configuration step. Both settings and options have values, in this case
        we can force static library if MT was specified as runtime
        """
        if self.settings.compiler == "Visual Studio" and \
           self.options.shared and "MT" in str(self.settings.compiler.runtime):
            self.options.shared = False

        if self.options.header_only:
            # Should be doable in conan_info() but the UX is not ready
            self.options.remove("shared")
            self.options.remove("fPIC")
            self.options.remove("python")

        if self.zip_bzip2_requires_needed:
            # if self.settings.os == "Linux" or self.settings.os == "Macos":
            #     self.requires("bzip2/1.0.6@camposs/stable")
            #     self.options["bzip2"].shared = self.options.shared
            self.requires("zlib/1.2.11@camposs/stable")
            self.options["zlib"].shared = self.options.shared

    def system_requirements(self):
        if not self.options.without_python:
            if os_info.is_linux:
                if os_info.with_apt:
                    # @Todo This should not be done here !!! conan should not install system packages ..
                    installer = SystemPackageTool()
                    if self.settings.arch == "x86" and tools.detected_architecture() == "x86_64":
                        arch_suffix = ':i386'
                        installer.install("g++-multilib")
                    else:
                        arch_suffix = ''
                    installer.install("%s%s" % ("%s-dev" % self.options.python, arch_suffix))
                # elif os_info.with_yum:
                #     installer = SystemPackageTool()
                #     if self.settings.arch == "x86" and tools.detected_architecture() == "x86_64":
                #         arch_suffix = '.i686'
                #         installer.install("glibc-devel.i686")
                #     else:
                #         arch_suffix = ''
                #     installer.install("%s%s" % ("lttng-tools", arch_suffix))
                #     installer.install("%s%s" % ("lttng-ust", arch_suffix))
                else:
                    self.output.warn("Could not determine package manager, skipping Linux system requirements installation.")

    def package_id(self):
        if self.options.header_only:
            self.info.header_only()

    def source(self):
        zip_name = "%s.zip" % self.folder_name if sys.platform == "win32" else "%s.tar.gz" % self.folder_name
        url = "https://dl.bintray.com/boostorg/release/%s/source/%s" % (self.upstream_version, zip_name)
        self.output.info("Downloading %s..." % url)
        tools.download(url, zip_name)
        tools.unzip(zip_name)
        os.unlink(zip_name)

    ##################### BUILDING METHODS ###########################

    def build(self):
        if self.options.header_only:
            self.output.warn("Header only package, skipping build")
            return

        if os_info.is_windows:
            tools.patch(base_path=os.path.join(self.build_folder, self.folder_name), patch_file="patches/fix_pcl_1.11_compiler_error_cuda.patch", strip=2)
        # fix for change to boost quaternion (made members private, but we want to subclass it and access it's members)
        # somehow this patch does not work :(((
        # tools.patch(base_path=os.path.join(self.build_folder, self.folder_name), patch_file='patches/quaternion_make_members_protected.patch', strip=1)

        # for now just replace the hopefully unique string in this file ..
        tools.replace_in_file(os.path.join(self.build_folder, self.folder_name, "boost", "math", "quaternion.hpp"), 
            """        private:
           T a, b, c, d;""",
            """        protected:
           T a, b, c, d;""")

        # tools.patch(base_path=os.path.join(self.build_folder, self.folder_name), patch_file='patches/fix_cond_waitfor_fibers01.patch', strip=1)

        # if self.settings.compiler == "Visual Studio":
        #     tools.replace_in_file(os.path.join(self.source_folder, self.folder_name, "boost/config/compiler/visualc.hpp"), 
        #         "#if (_MSC_VER > 1910)", '''#if (_MSC_VER > 1915)''')

        b2_exe = self.bootstrap()
        flags = self.get_build_flags()
        # Help locating bzip2 and zlib
        self.create_user_config_jam(self.build_folder)

        # JOIN ALL FLAGS
        b2_flags = " ".join(flags)
        full_command = "%s %s -j%s --abbreviate-paths -d2" % (b2_exe, b2_flags, tools.cpu_count())
        # -d2 is to print more debug info and avoid travis timing out without output
        sources = os.path.join(self.source_folder, self.folder_name)
        full_command += ' --debug-configuration --build-dir="%s"' % self.build_folder
        self.output.warn(full_command)

        with tools.vcvars(self.settings) if self.settings.compiler == "Visual Studio" else tools.no_op():
            with tools.chdir(sources):
                # to locate user config jam (BOOST_BUILD_PATH)
                with tools.environment_append({"BOOST_BUILD_PATH": self.build_folder}):
                    # To show the libraries *1
                    # self.run("%s --show-libraries" % b2_exe)
                    self.run(full_command)

    def get_build_flags(self):

        if tools.cross_building(self.settings):
            flags = self.get_build_cross_flags()
        else:
            flags = []
            if self.settings.arch == 'x86' and 'address-model=32' not in flags:
                flags.append('address-model=32')
            elif self.settings.arch == 'x86_64' and 'address-model=64' not in flags:
                flags.append('address-model=64')

        if self.settings.compiler == "gcc":
            flags.append("--layout=system")

        if self.settings.compiler == "Visual Studio" and self.settings.compiler.runtime:
            flags.append("runtime-link=%s" % ("static" if "MT" in str(self.settings.compiler.runtime) else "shared"))

        if self.settings.os == "Windows" and self.settings.compiler == "gcc":
            flags.append("threading=multi")

        flags.append("link=%s" % ("static" if not self.options.shared else "shared"))
        if self.settings.build_type == "Debug":
            flags.append("variant=debug")
        else:
            flags.append("variant=release")

        for libname in lib_list:
            if getattr(self.options, "without_%s" % libname):
                flags.append("--without-%s" % libname)

        # CXX FLAGS
        cxx_flags = []
        # fPIC DEFINITION
        if self.settings.compiler != "Visual Studio":
            if self.options.fPIC:
                cxx_flags.append("-fPIC")

        # Standalone toolchain fails when declare the std lib
        if self.settings.os != "Android":
            try:
                if str(self.settings.compiler.libcxx) == "libstdc++":
                    flags.append("define=_GLIBCXX_USE_CXX11_ABI=0")
                elif str(self.settings.compiler.libcxx) == "libstdc++11":
                    flags.append("define=_GLIBCXX_USE_CXX11_ABI=1")
                if "clang" in str(self.settings.compiler):
                    if str(self.settings.compiler.libcxx) == "libc++":
                        cxx_flags.append("-stdlib=libc++")
                        cxx_flags.append("-std=c++11")
                        flags.append('linkflags="-stdlib=libc++"')
                    else:
                        cxx_flags.append("-stdlib=libstdc++")
                        cxx_flags.append("-std=c++11")
            except:
                pass

        if self.settings.os == "iOS":
            arch = self.settings.get_safe('arch')

            cxx_flags.append("-DBOOST_AC_USE_PTHREADS")
            cxx_flags.append("-DBOOST_SP_USE_PTHREADS")
            cxx_flags.append("-fvisibility=hidden")
            cxx_flags.append("-fvisibility-inlines-hidden")
            cxx_flags.append("-fembed-bitcode")
            cxx_flags.extend(["-arch", tools.to_apple_arch(arch)])

            try:
                cxx_flags.append("-mios-version-min=%s" % self.settings.os.version)
                self.output.info("iOS deployment target: %s" % self.settings.os.version)
            except:
                pass

            flags.append("macosx-version=%s" % self.b2_macosx_version())

        cxx_flags = 'cxxflags="%s"' % " ".join(cxx_flags) if cxx_flags else ""
        flags.append(cxx_flags)

        return flags

    def get_build_cross_flags(self):
        arch = self.settings.get_safe('arch')
        flags = []
        self.output.info("Cross building, detecting compiler...")
        arch = "arm" if arch.startswith("arm") else arch
        arch = "x86" if arch == "x86_64" else arch
        flags.append('architecture=%s' % arch)
        bits = {"x86_64": "64", "armv8": "64"}.get(str(self.settings.arch), "32")
        flags.append('address-model=%s' % bits)
        if self.settings.get_safe('os').lower() in ('linux', 'android'):
            flags.append('binary-format=elf')

        if arch.startswith('arm'):
            if 'hf' in arch:
                flags.append('-mfloat-abi=hard')
            flags.append('abi=aapcs')
        elif arch in ["x86", "x86_64"]:
            pass
        else:
            raise Exception("I'm so sorry! I don't know the appropriate ABI for "
                            "your architecture. :'(")
        self.output.info("Cross building flags: %s" % flags)

        target = {"Windows": "windows",
                  "Macos": "darwin",
                  "Linux": "linux",
                  "Android": "android",
                  "iOS": "iphone",
                  "watchOS": "iphone",
                  "tvOS": "appletv",
                  "freeBSD": "freebsd"}.get(str(self.settings.os), None)

        if not target:
            raise Exception("Unknown target for %s" % self.settings.os)

        flags.append("target-os=%s" % target)
        return flags

    def create_user_config_jam(self, folder):
        """To help locating the zlib and bzip2 deps"""
        self.output.warn("Patching user-config.jam")

        compiler_command = os.environ.get('CXX', None)

        contents = ""
        if self.zip_bzip2_requires_needed:
            contents = "\nusing zlib : 1.2.11 : <include>%s <search>%s <name>%s ;" % (
                self.deps_cpp_info["zlib"].include_paths[0].replace('\\', '/'),
                self.deps_cpp_info["zlib"].lib_paths[0].replace('\\', '/'),
                self.deps_cpp_info["zlib"].libs[0])

            # contents += "\nusing bzip2 : 1.0.6 : <include>%s <search>%s <name>%s ;" % (
            #     self.deps_cpp_info["bzip2"].include_paths[0].replace('\\', '/'),
            #     self.deps_cpp_info["bzip2"].lib_paths[0].replace('\\', '/'),
            #     self.deps_cpp_info["bzip2"].libs[0])

        if not self.options.without_python:
            contents += "\nusing python : {} : {} ;".format(sys.version[:3], sys.executable.replace('\\', '/'))

        toolset, version, exe = self.get_toolset_version_and_exe()
        exe = compiler_command or exe  # Prioritize CXX
        # Specify here the toolset with the binary if present if don't empty parameter : :
        contents += '\nusing "%s" : "%s" : ' % (toolset, version)
        contents += ' "%s"' % exe.replace("\\", "/")

        contents += " : \n"
        if "AR" in os.environ:
            contents += '<archiver>"%s" ' % tools.which(os.environ["AR"]).replace("\\", "/")
        if "RANLIB" in os.environ:
            contents += '<ranlib>"%s" ' % tools.which(os.environ["RANLIB"]).replace("\\", "/")
        if "CXXFLAGS" in os.environ:
            contents += '<cxxflags>"%s" ' % os.environ["CXXFLAGS"]
        if "CFLAGS" in os.environ:
            contents += '<cflags>"%s" ' % os.environ["CFLAGS"]
        if "LDFLAGS" in os.environ:
            contents += '<ldflags>"%s" ' % os.environ["LDFLAGS"]

        if self.settings.os == "iOS":
            sdk_name = tools.apple_sdk_name(self.settings)
            contents += '<striper> <root>%s <architecture>%s <target-os>iphone' % (
                self.bjam_darwin_root(sdk_name), self.bjam_darwin_architecture(sdk_name))

        contents += " ;"

        self.output.warn(contents)
        filename = "%s/user-config.jam" % folder
        tools.save(filename,  contents)

    def get_toolset_version_and_exe(self):
        compiler_version = str(self.settings.compiler.version)
        compiler = str(self.settings.compiler)
        if self.settings.compiler == "Visual Studio":
            cversion = self.settings.compiler.version
            _msvc_version = "14.2" if cversion == "16" else ("14.1" if cversion == "15" else "%s.0" % cversion)
            return "msvc", _msvc_version, ""
        elif compiler == "gcc" and compiler_version[0] >= "5":
            # For GCC >= v5 we only need the major otherwise Boost doesn't find the compiler
            # The NOT windows check is necessary to exclude MinGW:
            if not tools.which("g++-%s" % compiler_version[0]):
                # In fedora 24, 25 the gcc is 6, but there is no g++-6 and the detection is 6.3.1
                # so b2 fails because 6 != 6.3.1. Specify the exe to avoid the smart detection
                executable = "g++"
            else:
                executable = ""
            return compiler, compiler_version[0], executable
        elif str(self.settings.compiler) in ["clang", "gcc"]:
            # For GCC < v5 and Clang we need to provide the entire version string
            return compiler, compiler_version, ""
        elif self.settings.compiler == "apple-clang":
            if self.settings.os == "iOS":
                cc = tools.XCRun(self.settings, tools.apple_sdk_name(self.settings)).cc
                return "darwin", self.bjam_darwin_toolchain_version(), cc
            else:
                return "clang", compiler_version, ""
        elif self.settings.compiler == "sun-cc":
            return "sunpro", compiler_version, ""
        else:
            return compiler, compiler_version, ""

    ##################### BOOSTRAP METHODS ###########################
    def _get_boostrap_toolset(self):
        if self.settings.os == "Windows" and self.settings.compiler == "Visual Studio":
            comp_ver = self.settings.compiler.version
            return "vc%s" % ("142" if comp_ver == "16" else ("141" if comp_ver == "15" else comp_ver))

        with_toolset = {"apple-clang": "darwin"}.get(str(self.settings.compiler),
                                                     str(self.settings.compiler))
        return with_toolset

    def bootstrap(self):
        folder = os.path.join(self.source_folder, self.folder_name, "tools", "build")
        try:
            bootstrap = "bootstrap.bat" if tools.os_info.is_windows else "./bootstrap.sh"
            with tools.vcvars(self.settings) if self.settings.compiler == "Visual Studio" else tools.no_op():
                self.output.info("Using %s %s" % (self.settings.compiler, self.settings.compiler.version))
                with tools.chdir(folder):
                    cmd = "%s %s" % (bootstrap, self._get_boostrap_toolset())
                    self.output.info(cmd)
                    self.run(cmd)
        except Exception as exc:
            self.output.warn(str(exc))
            if os.path.exists(os.path.join(folder, "bootstrap.log")):
                self.output.warn(tools.load(os.path.join(folder, "bootstrap.log")))
            raise
        return os.path.join(folder, "b2.exe") if tools.os_info.is_windows else os.path.join(folder, "b2")

    ####################################################################

    def package(self):
        # This stage/lib is in source_folder... Face palm, looks like it builds in build but then
        # copy to source with the good lib name
        out_lib_dir = os.path.join(self.folder_name, "stage", "lib")
        self.copy(pattern="*", dst="include/boost", src="%s/boost" % self.folder_name)
        if not self.options.shared:
            self.copy(pattern="*.a", dst="lib", src=out_lib_dir, keep_path=False)
        self.copy(pattern="*.so", dst="lib", src=out_lib_dir, keep_path=False, symlinks=True)
        self.copy(pattern="*.so.*", dst="lib", src=out_lib_dir, keep_path=False, symlinks=True)
        self.copy(pattern="*.dylib*", dst="lib", src=out_lib_dir, keep_path=False)
        self.copy(pattern="*.lib", dst="lib", src=out_lib_dir, keep_path=False)
        self.copy(pattern="*.dll", dst="bin", src=out_lib_dir, keep_path=False)

        # When first call with source do not package anything
        if not os.path.exists(os.path.join(self.package_folder, "lib")):
            return

        self.renames_to_make_cmake_find_package_happy()

    def renames_to_make_cmake_find_package_happy(self):
        if not self.options.skip_lib_rename:
            # CMake findPackage help
            renames = []
            for libname in os.listdir(os.path.join(self.package_folder, "lib")):
                new_name = libname
                libpath = os.path.join(self.package_folder, "lib", libname)
                if "-" in libname:
                    new_name = libname.split("-", 1)[0] + "." + libname.split(".")[-1]
                    if new_name.startswith("lib"):
                        new_name = new_name[3:]
                renames.append([libpath, os.path.join(self.package_folder, "lib", new_name)])

            for original, new in renames:
                if original != new and not os.path.exists(new):
                    self.output.info("Rename: %s => %s" % (original, new))
                    os.rename(original, new)

    def package_info(self):
        gen_libs = tools.collect_libs(self)

        # List of lists, so if more than one matches the lib like serialization and wserialization
        # both will be added to the list
        ordered_libs = [[] for _ in range(len(lib_list))]

        # The order is important, reorder following the lib_list order
        missing_order_info = []
        for real_lib_name in gen_libs:
            for pos, alib in enumerate(lib_list):
                if os.path.splitext(real_lib_name)[0].split("-")[0].endswith(alib):
                    ordered_libs[pos].append(real_lib_name)
                    break
            else:
                # self.output.info("Missing in order: %s" % real_lib_name)
                if "_exec_monitor" not in real_lib_name:  # https://github.com/bincrafters/community/issues/94
                    missing_order_info.append(real_lib_name)  # Assume they do not depend on other

        # Flat the list and append the missing order
        self.cpp_info.libs = [item for sublist in ordered_libs
                                      for item in sublist if sublist] + missing_order_info

        if self.options.without_test:  # remove boost_unit_test_framework
            self.cpp_info.libs = [lib for lib in self.cpp_info.libs if "unit_test" not in lib]

        self.output.info("LIBRARIES: %s" % self.cpp_info.libs)
        self.output.info("Package folder: %s" % self.package_folder)

        if not self.options.header_only and self.options.shared:
            self.cpp_info.defines.append("BOOST_ALL_DYN_LINK")
        else:
            self.cpp_info.defines.append("BOOST_USE_STATIC_LIBS")

        if not self.options.header_only:
            if not self.options.without_python:
                if not self.options.shared:
                    self.cpp_info.defines.append("BOOST_PYTHON_STATIC_LIB")

            if self.settings.compiler == "Visual Studio":
                if self.options.magic_autolink == False:
                    # DISABLES AUTO LINKING! NO SMART AND MAGIC DECISIONS THANKS!
                    self.cpp_info.defines.extend(["BOOST_ALL_NO_LIB"])
                    self.output.info("Disabled magic autolinking (smart and magic decisions)")
                else:
                    self.output.info("Enabled magic autolinking (smart and magic decisions)")

                # https://github.com/conan-community/conan-boost/issues/127#issuecomment-404750974
                self.cpp_info.libs.append("bcrypt")
            elif self.settings.os == "Linux":
                # https://github.com/conan-community/conan-boost/issues/135
                self.cpp_info.libs.append("pthread")

        self.env_info.BOOST_ROOT = self.package_folder

    def b2_macosx_version(self):
        sdk_name = tools.apple_sdk_name(self.settings)
        if sdk_name == None:
            raise ValueError("Bad apple SDK name! "
                + "b2_macosx_version could be called only to build for Macos/iOS")

        sdk_version = self._xcrun_sdk_version(sdk_name)

        return {"macosx": sdk_version,
                 "iphoneos": "iphone-%s" % sdk_version,
                 "iphonesimulator": "iphonesim-%s" % sdk_version
               }.get(sdk_name, "%s-%s" % (sdk_name, sdk_version))

    def bjam_darwin_root(self, sdk_name):
        return os.path.join(tools.XCRun(self.settings, sdk_name).sdk_platform_path, 'Developer')

    def bjam_darwin_toolchain_version(self):
        sdk_name = tools.apple_sdk_name(self.settings)
        if sdk_name == None:
            raise ValueError("Bad apple SDK name! "
                + "bjam_darwin_toolchain_version could be called only to build for Macos/iOS")

        sdk_version = self._xcrun_sdk_version(sdk_name)

        return {"macosx": sdk_version}.get(sdk_name, "%s~%s" % (sdk_version, sdk_name))

    def bjam_darwin_architecture(self, sdk_name):
        return "x86" if sdk_name in ["macosx", "iphonesimulator"] else "arm"

    def _xcrun_sdk_version(self, sdk_name):
        """returns devault SDK version for specified SDK name which can be returnd
        by `self.xcrun_sdk_name()`"""
        return tools.XCRun(self.settings, sdk_name).sdk_version
