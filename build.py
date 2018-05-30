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


def get_default_vars():
    username = os.getenv("CONAN_USERNAME", "ulricheck")
    channel = os.getenv("CONAN_CHANNEL", "stable")
    version = get_version_from_recipe()
    return username, channel, version


def is_ci_running():
    return os.getenv("APPVEYOR_REPO_NAME", "") or os.getenv("TRAVIS_REPO_SLUG", "")


def get_ci_vars():
    reponame_a = os.getenv("APPVEYOR_REPO_NAME","")
    repobranch_a = os.getenv("APPVEYOR_REPO_BRANCH","")

    reponame_t = os.getenv("TRAVIS_REPO_SLUG","")
    repobranch_t = os.getenv("TRAVIS_BRANCH","")

    username, _ = reponame_a.split("/") if reponame_a else reponame_t.split("/")
    channel, version = repobranch_a.split("/") if repobranch_a else repobranch_t.split("/")
    return username, channel, version


def get_env_vars():
    return get_ci_vars() if is_ci_running() else get_default_vars()


def get_os():
    return platform.system().replace("Darwin", "Macos")


# for ubitrack we want a stripped down version of boost
# therefore we're adding new builds that create the needed artefacts
def add_ubitrack_build_options(items):
    ubitrack_opts = {}
    ubitrack_opts['Boost: without_atomic'] = True
    ubitrack_opts['Boost:without_container'] = True
    ubitrack_opts['Boost:without_context'] = True
    ubitrack_opts['Boost:without_coroutine'] = True
    ubitrack_opts['Boost:without_coroutine2'] = True
    ubitrack_opts['Boost:without_exception'] = True
    ubitrack_opts['Boost:without_graph'] = True
    ubitrack_opts['Boost:without_graph_parallel'] = True
    ubitrack_opts['Boost:without_locale'] = True
    ubitrack_opts['Boost:without_log'] = True
    ubitrack_opts['Boost:without_mpi'] = True
    ubitrack_opts['Boost:without_signals'] = True
    ubitrack_opts['Boost:without_timer'] = True
    ubitrack_opts['Boost:without_wave'] = True
    builds = items[:]
    for settings, options, env_vars, build_requires, reference in items:
        # add config for ubitrack
        options_extended = options.copy()
        options_extended.update(ubitrack_opts)
        builds.append([settings, options_extended, env_vars, build_requires, reference])
    return builds



if __name__ == "__main__":
    name = get_name_from_recipe()
    username, channel, version = get_env_vars()
    reference = "{0}/{1}".format(name, version)

    builder = ConanMultiPackager(
        reference=reference,
        upload_only_when_stable=True,
        stable_branch_pattern="stable/*")

    builder.add_common_builds(shared_option_name=name + ":shared", pure_c=False)

    if platform.system() == "Windows":
        filtered_builds = []
        for settings, options, env_vars, build_requires, reference in builder.items:
            if settings["compiler"] != "Visual Studio" or options[name + ":shared"]:
                filtered_builds.append([settings, options, env_vars, build_requires, reference])
        builder.builds = filtered_builds

    builder.builds = add_ubitrack_build_options(builder.items)
    builder.run()