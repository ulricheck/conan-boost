#!/usr/bin/env python
# -*- coding: utf-8 -*-

from conan.packager import ConanMultiPackager
import os
import re
import platform


def get_value_from_recipe(search_string):
    with open("conanfile.py", "r") as conanfile:
        contents = conanfile.read()
        result = re.search(search_string, contents)
    return result


def get_name_from_recipe():
    return get_value_from_recipe(r'''name\s*=\s*["'](\S*)["']''').groups()[0]


def get_version_from_recipe():
    return get_value_from_recipe(r'''version\s*=\s*["'](\S*)["']''').groups()[0]



if __name__ == "__main__":
    name = get_name_from_recipe()
    reference = "{0}/{1}".format(name, version)

    builder = ConanMultiPackager(
        reference=reference,
        upload_only_when_stable=True,
        stable_branch_pattern="stable/*")

    builder.add_common_builds(shared_option_name=name + ":shared")

    if platform.system() == "Windows":
        filtered_builds = []
        for build in builder.builds:
            if build.settings["compiler"] != "Visual Studio" or build.options[name + ":shared"]:
                filtered_builds.append(build)
        builder.builds = filtered_builds

    builder.run()