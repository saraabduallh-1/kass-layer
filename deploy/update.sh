#!/bin/sh
# Updates kass.arai.center from GitHub. Runs on the server:
#   ssh renad@arai.center 'sh ~/apps/kass/repo/deploy/update.sh'
# First time (no copy of the repo on the server yet):
#   ssh renad@arai.center 'git clone -b enrichment-pass1 --depth 1 https://github.com/saraabduallh-1/kass-layer.git ~/apps/kass/repo && sh ~/apps/kass/repo/deploy/update.sh'
# Takes the branch as it is on GitHub (the server copy is never edited), builds the image from it and restarts only kass_app.
set -e
BRANCH=${1:-enrichment-pass1}
REPO="$HOME/apps/kass/repo"
cd "$REPO"
git fetch -q --depth 1 origin "$BRANCH"
git reset -q --hard FETCH_HEAD
echo "deploying $(git log -1 --format='%h %s')"
podman build -q --format docker -t kass:latest "$REPO"
cd "$HOME/apps/kass" && podman compose up -d --force-recreate app
echo "done: https://kass.arai.center"
