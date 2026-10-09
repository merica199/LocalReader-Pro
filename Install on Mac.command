#!/bin/bash
# Double-click this in Finder to install LocalReader Pro into Applications.
# Everything it does is described at the top of installers/mac/install.sh.
exec /bin/bash "$(dirname "$0")/installers/mac/install.sh" "$@"
