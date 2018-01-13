
# conan-boost

[Conan.io](https://conan.io) package for Boost library

## Reuse the packages

### Basic setup

    $ conan install Boost/1.64.0@camposs/stable

### Project setup

If you handle multiple dependencies in your project is better to add a *conanfile.txt*

    [requires]
    Boost/1.64.0@camposs/stable

    [options]
    Boost:shared=true # false
    # Take a look for all available options in conanfile.py

    [generators]
    txt
    cmake

Complete the installation of requirements for your project running:</small></span>

    conan install .

Project setup installs the library (and all his dependencies) and generates the files *conanbuildinfo.txt* and *conanbuildinfo.cmake* with all the paths and variables that you need to link with your dependencies.