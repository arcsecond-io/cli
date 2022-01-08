#!/usr/bin/env sh

# abort on errors
set -e

# build
npm run docs:build

# navigate into the build output directory
cd docs/.vitepress/dist

echo 'cli.arcsecond.io' > CNAME

git config user.email "team@arcsecond.io"
git config user.name "gh actions bot"
git config init.defaultBranch "master"

git init
git add -A
git commit -m 'deploy'

git remote set-url origin https://arcsecond-io:$GITHUB_TOKEN@github.com/arcsecond-io/cli
git push -f origin master:gh-pages

# if you are deploying to https://<USERNAME>.github.io
# git push -f git@github.com:arcsecond-io/arcsecond-io.github.io.git master

# if you are deploying to https://<USERNAME>.github.io/<REPO>
# git push -f git@github.com:arcsecond-io/cli.git master:gh-pages

cd -

