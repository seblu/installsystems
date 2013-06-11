==
is
==

--------------
InstallSystems
--------------

:Author: Sébastien Luttringer <sebastien.luttringer@smartjog.com>
:Manual section: 1

SYNOPSIS
========

is [options...] command [args...]

SUMMARY
=======

The InstallSystems is a systems deploy tool. It can easily setup hosts or VMs. This tool gives access to versionned images of systems and configuration scripts. It is a complete solution for mass deployment. It regroups tools for image making, repository management, and easy installing.

You can use InstallSystems with already existent repositories/images or you can make yours using the appropriate is command.

OPTIONS
=======
-h, --help
    show an help message and exit

-V, --version
    show InstallSystems version

-v {0,1,2}, --verbosity {0,1,2}
    show InstallSystems version

-d, --debug
    enable debug mode

-q, --quiet
    enable quiet mode

-c *CONFIG*, --config *CONFIG*
    define path to configuration file

-R *REPO_CONFIG*, --repo-config *REPO_CONFIG*
    define path to repositories configuration file

-s *REPO*, --repo-search *REPO*
    search for images inside those repositories

-f *REPO_FILTER*, --repo-filter *REPO_FILTER*
    filter repositories by name

-r *REPO_PATH*, --repo-path *REPO_PATH*
    define *REPO_PATH* as a temporary repository

-T *SECONDS*, --repo-timeout *SECONDS*
    set repositories access timeout to *SECONDS*

--no-cache
    do not use persistent database caching

--no-sync
    do not sync repository database cache

--no-color
    do not display color output

--nice NICE
    set the *NICE* value for the process

--ionice-class {none,rt,be,idle}
    ionice class of the process (default: none)

--ionice-level IONICE_LEVEL
    set the *IONICE_LEVEL* for the process

<remote_image>
    an InstallSystems *image* selected with the following pattern:

    [repository/][image][:version] (Note that the repository can be local)

    Example: stable/debian\*:\*, stable/, stable/:4, :\*dev, debian

<local_image>
    an InstallSystems *image*, same as <remote_image>, but the repository *must* be local

<image>
    an InstallSystems *image*, it's a <remote_image> or a path to a packaged image


COMMANDS
========

Please note that you can display specific help messages for all of
these commands by using the --help argument after the command name.

add [-h] [-p] *repository* *image_path*...
    Add a local *image* to a local *repository*.

    -p, --preserve
        do not remove *image* after adding it to the *repository*


build [-h] [-c] [-C] [-f] [-p] [-s] [*path*]...
    Check and build the InstallSystems source image in *path* (by default, in the current directory).

    -c, --no-check
        do not check scripts compilation

    -C, --chdir
        build image inside source image directory, not in the current one

    -f, --force
        overwrite existing images

    -p, --payload
        overwrite existing payloads

    -s, --no-script
        do not run build scripts


cat [-h] <image> *file*...
    Display one *file* (or more) from *image*. Globbing is allowed for files matching.


changelog [-h] [-v]  <image>...
    Display the last changelog entry for one *image* (or more).

    -v, --all-version
        display the whole changelog


check [-h] *repository*
    Check a local *repository* for missing, unreferenced and corrupted files.


chroot [-h] [-m] [-s *SHELL*\ ] *path*
    Chroot inside *path*. This is especially useful to update system images. This mounts filesystems (/proc, /sys, /dev, /dev/pts, /dev/shm), modify a few config files (resolv.conf, mtab) and finally executes a shell in your chroot (default: /bin/bash)

    -m, --no-mount
        disable mounting of /{proc,dev,sys}

    -s *SHELL*\ , --shell *SHELL*
        shell to call inside the chroot


clean [-h] [-f] *repository*...
    Clean-up one local *repository* (or more). This will remove files that are no longer referenced in the repository database.

    -f, --force
        do not prompt before cleaning


copy [-h] [-f] <remote_image>... *repository*
    Copy one *image* (or more) to another local **repository**.

     -f, --force
         overwrite existing images without prompting


del [-h] [-f] [-p] <local_image>...
    Delete one *image* (or more) from its repository.

    -f, --force
        delete images without prompting

    -p, --preserve
        do not remove payloads from the repository


diff [-h] *object* *object*
    Show diff between two repositories or images.


extract [-h] [-f] [-g] [-p] <image> *path*
    Extract an InstallSystems *image* into *path*.

    -f, --force
        overwrite existing destination

    -g, --gen-description
        generate a description file from metadata

    -p, --payload
        extract payloads


get [-h] [-f] [-I] [-p] <remote_image>...
    Download a remote InstallSystems *image* in current directory.

    -f, --force
        overwrite existing destination

    -I, --no-image
        do not get the image (should be combined with -p)

    -p, --payload
        also get payloads


help [-h]
    Show help.


info [-h] [-a] [-j] [-c] [-f] [-p] <image>...
    Display information about one *image* (or more).

    -a, --all
        display all information available

    -j, --json
        display all information formated in json

    -c, --changelog
        display image changelog

    -f, --files
        display image files

    -p, --payloads
        display image payloads


init [-h] *repository*...
    Create one empty *repository* (or more).


install [--dry-run] <image>
    Install *image*. Each *image* may have specific options. Typically, each one will display a list of available options when using the **--help** argument. In case of trouble during the install you should contact the author of the image. You can find this info in its description file.

    --dry-run
        do not execute setup scripts


list [-h] [-A] [-d] [-D] [-f] [-j] [-i] [-l] [-m] [-s] [-u] [<remote_image>...]
    List available *images*. By default, it displays the image name and its repository, ordered by repositories/images/version.

    -A, --author
        display image author

    -d, --date
        display image date

    -D, --description
        display image description

    -f, --format
        display image format

    -j, --json
        output is formated in json

    -i, --is-min-version
        display minimum Installsystems version required

    -l, --long
        long display

    -m, --md5
        display image md5

    -s, --size
        display image size

    -u, --url
        display image url


motd [-h] [--edit] *repository*
    Display MOTD of a repository

    --edit
        edit the MOTD of the repository


move [-h] [-f] <local_image>... *repository*
    Move one *image* (or more) to another *repository*.

    -f, --force
        move *image* without confirmation


new [-h] [-f] *path*
    Create a new source image in *path*. It creates the base directories (parser, setup, payload) and a description template. Moreover this command creates samples files for setup, parser and changelog. It also set executable rights on scripts.

    -f, --force
        overwrite existing source image


payload [-h] [-j] [-i] [md5_pattern]...
    List available payloads matching *md5_pattern* (Default: match everything)

    -j, --json
        output is formated in json

    -i, --images
        list images using payload


prepare_chroot [-h] [-m] *path*
    Prepare to chroot in *path*.

    -m, --no-mount
        disable mounting of /{proc,dev,sys}


repo [-h] [-j] [-l|-r] [-o|-O] [-s] [-u] [-U] [-v] [--purge] [repository]...
    List available repositories. By defaut, only names are displayed.

    -j, --json
        output is formated in json

    -l, --local
        list local repositories (filter)

    -r, --remote
        list remote repositories (filter)

    -o, --online
        list online repositories (filter)

    -O, --offline
        list offline repositories (filter)

    -s, --state
        display repository state (online/offline/local/remote)

    -u, --url
        display repository url

    -U, --uuid
        display repository UUID

    -v, --version
        display repository version

    --purge
        remove cache databases


search [-h] *pattern*
    Search *pattern* in repositories.


unprepare_chroot [-h] [-m] *path*
    Remove preparation of a chroot in *path*.

    -m, --no-umount
        disable unmouting of /{proc,dev,sys}


upgrade_db [-h] *repository*
    Upgrade repository's database to the current database version


version [-h]
    Print InstallSystems version.


EXAMPLES
========

Setup a real host and then reboot it.

    is install debian-smartjog -n bobby.seblu.net --disks /dev/sda --reboot

Create of a new image named foobar.

    is new foobar

Build the cdn-fw image

    is build ./images/cdn-fw

IMAGES
======

InstallSystems use two kind of images:

**source image**

     Each image available in repositories has to be built. The image before building is called a source image. In a source image, there are typically five directories and three files.

    build/
        Scripts to customize the build process for the image.

    parser/
        Scripts adding specific options for the image are in this directory.

    setup/
        The scripts with logical steps of the install are in this directory.

    lib/
        Python modules needed to build and/or to install the image

    payload/
        This directory embeds one or more payloads (typically rootfs) for the image.

    description
        It defines information about image.

    changelog
        The changelog file lists modifications of the image.

**description**

    The description file contains name, version, author, description and InstallSystems minimum version needed.

       |
       | [image]
       | name = foo
       | version = 42
       | description = example image
       | author = Toto <toto@example.com>
       | is_min_version = 9

    Description file can also specify the compressor to use for payloads. Four compressors are available: 'none' (no compression), 'gzip', 'bzip2' and 'xz'. For each compressor, you can declare a globbing pattern to select specific payloads (use commas to separate patterns). Be careful, order matters. Here is an example:

        |
        | [compressor]
        | gzip = \*
        | xz = rootfs\*
        | none = \*.gz, \*.bz2, \*.xz

    The default compressor will be gzip, xz will be used for payload matching rootfs\* and each payload whose name ends with .gz, .bz2 and .xz will not be compressed.

**packaged image**

    Built images are called packaged images. They are versionned, compressed and ready to deploy. Like source images, package images still make the difference between scripts and payloads. But it doesn't make difference between build, parser and setup scripts. In fact you will have at least two tarballs:

    image_name.isimage
        This tarball contains build/, parser/, setup/, description and changelog.

    image_name.isdata
        This tarball contains one payload from payload/

REPOSITORIES
============

InstallSystems manages images with repositories.

An InstallSystems repository use a SQLite3 database (db), a last file (timestamp of last db modification) and MD5s of images. Repositories are reachable by HTTP(S), FTP and SSH. This allows you to easily access images.
Also, please note that you can only modify local repositories.
