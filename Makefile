# =============================================================================
# @file    Makefile
# @brief   Makefile for some steps in creating new releases on GitHub
# @author  Michael Hucka
# @date    2020-08-11
# @license Please see the file named LICENSE in the project directory
# @website https://github.com/mhucka/zowie
# =============================================================================

.ONESHELL: 				# Run all commands in the same shell.
.SHELLFLAGS += -e			# Exit at the first error.

# This Makefile uses syntax that needs at least GNU Make version 3.82.
# The following test is based on the approach posted by Eldar Abusalimov to
# Stack Overflow in 2012 at https://stackoverflow.com/a/12231321/743730

ifeq ($(filter undefine,$(value .FEATURES)),)
$(error Unsupported version of Make. \
    This Makefile does not work properly with GNU Make $(MAKE_VERSION); \
    it needs GNU Make version 3.82 or later)
endif

# Before we go any further, test if certain programs are available.
# The following is based on the approach posted by Jonathan Ben-Avraham to
# Stack Overflow in 2014 at https://stackoverflow.com/a/25668869

programs_needed = curl gh git jq sed pyinstaller
TEST := $(foreach p,$(programs_needed),\
	  $(if $(shell which $(p)),_,$(error Cannot find program "$(p)")))

# Set some basic variables.  These are quick to set; we set additional
# variables using "vars" but only when the others are needed.

name     := $(strip $(shell awk -F "=" '/^name/ {print $$2}' setup.cfg))
version  := $(strip $(shell awk -F "=" '/^version/ {print $$2}' setup.cfg))
url      := $(strip $(shell awk -F "=" '/^url/ {print $$2}' setup.cfg))
desc     := $(strip $(shell awk -F "=" '/^description / {print $$2}' setup.cfg))
author   := $(strip $(shell awk -F "=" '/^author / {print $$2}' setup.cfg))
email    := $(strip $(shell awk -F "=" '/^author_email/ {print $$2}' setup.cfg))
license  := $(strip $(shell awk -F "=" '/^license / {print $$2}' setup.cfg))
app_name := $(strip $(shell python3 -c 'print("$(name)".title()+".app")'))
platform := $(strip $(shell python3 -c 'import sys; print(sys.platform)'))
os       := $(subst $(platform),darwin,macos)
branch   := $(shell git rev-parse --abbrev-ref HEAD)
initfile := $(name)/__init__.py
distdir  := dist/$(os)
builddir := build/$(os)
zipfile  := dist/$(os)/$(name)-$(version)-$(os).zip

# Color codes used in messages below.
green	  := $(shell tput setaf 2)
reset	  := $(shell tput sgr0)


# Print help if no command is given ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

help:
	@echo 'Available commands:'
	@echo ''
	@echo 'make'
	@echo 'make help'
	@echo '  Print this summary of available commands.'
	@echo ''
	@echo 'make report'
	@echo '  Print variables set in this Makefile from various sources.'
	@echo '  This is useful to verify the values that have been parsed.'
	@echo ''
	@echo 'make release'
	@echo '  Do a release on GitHub. This will push changes to GitHub,'
	@echo '  open an editor to let you edit release notes, and run'
	@echo '  "gh release create" followed by "gh release upload".'
	@echo '  Note: this will NOT upload to PyPI, nor create binaries.'
	@echo ''
	@echo 'make update-doi'
	@echo '  Update the DOI inside the README.md file.'
	@echo '  This is only to be done after doing a "make release".'
	@echo ''
	@echo 'make binaries'
	@echo '  Create binaries (both pyinstaller and zipapps).'
	@echo ''
	@echo 'make upload-binaries'
	@echo '  Upload binaries to GitHub.'
	@echo ''
	@echo 'make packages'
	@echo '  Create the distribution files for PyPI.'
	@echo '  Do this manually to check that everything looks okay before.'
	@echo '  After doing this, do a "make test-pypi".'
	@echo ''
	@echo 'make test-pypi'
	@echo '  Upload distribution to test.pypi.org.'
	@echo '  Do this before doing "make pypi" for real.'
	@echo ''
	@echo 'make pypi'
	@echo '  Upload distribution to pypi.org.'
	@echo ''
	@echo 'make clean'
	@echo '  Clean up various files generated by this Makefile.'


# Gather additional values we sometimes need ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
#
# These variables take longer to compute, and for some actions like "make help"
# they are unnecessary and annoying to wait for.

.SILENT: vars
vars:
	$(info Gathering data -- this takes a few moments ...)
	$(eval repo	 := $(strip $(shell gh repo view | head -1 | cut -f2 -d':')))
	$(eval api_url   := https://api.github.com)
	$(eval id	 := $(shell curl -s $(api_url)/repos/$(repo) | jq '.id'))
	$(eval id_url	 := https://data.caltech.edu/badge/latestdoi/$(id))
	$(eval doi_url	 := $(shell curl -sILk $(id_url) | grep Locat | cut -f2 -d' '))
	$(eval doi	 := $(subst https://doi.org/,,$(doi_url)))
	$(eval doi_tail  := $(lastword $(subst ., ,$(doi))))
	$(info Gathering data -- this takes a few moments ... Done.)

# Note: the seemingly-misaligned equals signs in the code below are not really
# misaligned; it's adjusted for differences in tabs & spaces in the output.
report: vars
	@$(info $(green)os$(reset)	  = $(os))
	$(info $(green)name$(reset)	  = $(name))
	$(info $(green)version$(reset)	  = $(version))
	$(info $(green)url$(reset)	  = $(url))
	$(info $(green)desc$(reset)	  = $(desc))
	$(info $(green)author$(reset)	  = $(author))
	$(info $(green)email$(reset)	  = $(email))
	$(info $(green)license$(reset)	  = $(license))
	$(info $(green)branch$(reset)	  = $(branch))
	$(info $(green)repo$(reset)	  = $(repo))
	$(info $(green)id$(reset)	  = $(id))
	$(info $(green)id_url$(reset)	  = $(id_url))
	$(info $(green)doi_url$(reset)	  = $(doi_url))
	$(info $(green)doi$(reset)	  = $(doi))
	$(info $(green)doi_tail$(reset)  = $(doi_tail))
	$(info $(green)initfile$(reset)  = $(initfile))
	$(info $(green)distdir$(reset)	  = $(distdir))
	$(info $(green)builddir$(reset)  = $(builddir))


# make binaries ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

binaries: | vars $(distdir)/$(app_name)

dependencies:;
	pip3 install -r requirements.txt

pyinstaller $(distdir)/$(app_name): | vars dependencies run-pyinstaller make-zip

run-pyinstaller: vars
	@mkdir -p $(distdir)
	pyinstaller --distpath $(distdir) --clean --noconfirm pyinstaller-$(os).spec

make-zip: run-pyinstaller
	$(eval comments_file := $(shell mktemp /tmp/comments-$(name).XXXX))
	cat <<- EOF > $(comments_file)
	┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
	┃ This Zip archive file includes a self-contained, runnable ┃
	┃ version of the program Zowie ("ZOtero link WrItEr") for   ┃
	┃ macOS. To learn more about Zowie, please visit this site: ┃
	┃                                                           ┃
	┃              https://mhucka.github.io/zowie/              ┃
	┃                                                           ┃
	┗━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┛
	EOF
	zip $(zipfile) $(distdir)/$(name)
	zip -z $(zipfile) < $(comments_file)
	-rm -f $(comments_file)

shiv zipapps: | run-shiv

run-shiv:;
	@mkdir -p dist
	dev/scripts/create-pyz dist 3.8.2
	dev/scripts/create-pyz dist 3.9.5
	dev/scripts/create-pyz dist 3.10.0

build-darwin: $(distdir)/$(app_name) # $(about-file) $(help-file) # NEWS.html
#	packagesbuild dev/installer-builders/macos/packages-config/zowie.pkgproj
#	mv dist/zowie-mac.pkg dist/zowie-$(release)-macos-$(macos_vers).pkg


# make install ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

install:
	python3 install -e .[dev]


# make release ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

release: | test-branch release-on-github print-instructions

test-branch:
ifneq ($(branch),main)
	$(error Current git branch != main. Merge changes into main first!)
endif

update-init:
	@sed -i .bak -e "s|^\(__version__ *=\).*|\1 '$(version)'|"  $(initfile)
	@sed -i .bak -e "s|^\(__description__ *=\).*|\1 '$(desc)'|" $(initfile)
	@sed -i .bak -e "s|^\(__url__ *=\).*|\1 '$(url)'|"	    $(initfile)
	@sed -i .bak -e "s|^\(__author__ *=\).*|\1 '$(author)'|"    $(initfile)
	@sed -i .bak -e "s|^\(__email__ *=\).*|\1 '$(email)'|"	    $(initfile)
	@sed -i .bak -e "s|^\(__license__ *=\).*|\1 '$(license)'|"  $(initfile)

update-meta:
	$(eval date := $(shell date "+%F"))
	@sed -i .bak -e "/version/ s/[0-9].[0-9][0-9]*.[0-9][0-9]*/$(version)/" codemeta.json
	@sed -i .bak -e "/softwareVersion/ s/[0-9].[0-9][0-9]*.[0-9][0-9]*/$(version)/" codemeta.json
	@sed -i .bak -e "/datePublished/ s/[0-9][0-9-]*/$(date)/" codemeta.json

update-citation:
	$(eval date := $(shell date "+%F"))
	@sed -i .bak -e "/^date-released/ s/[0-9][0-9-]*/$(date)/" CITATION.cff
	@sed -i .bak -e "/^version/ s/[0-9].[0-9][0-9]*.[0-9][0-9]*/$(version)/" CITATION.cff

edited := codemeta.json $(initfile) CITATION.cff

commit-updates:
	git add $(edited)
	git diff-index --quiet HEAD $(edited) || \
	    git commit -m"Update stored version number" $(edited)

release-on-github: | update-init update-meta update-citation commit-updates
	$(eval tmp_file := $(shell mktemp /tmp/release-notes-$(name).XXXX))
	git push -v --all
	git push -v --tags
	@$(info ┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓)
	@$(info ┃ Write release notes in the file that gets opened in your   ┃)
	@$(info ┃ editor. Close the editor to complete the release process.  ┃)
	@$(info ┗━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┛)
	sleep 2
	$(EDITOR) $(tmp_file)
	gh release create v$(version) -t "Release $(version)" -F $(tmp_file)
	-rm -f $(tmp_file)

upload-binaries: | vars binaries
	gh release upload v$(version) dist/$(name).zip
	gh release upload v$(version) dist/*/$(name)-${version}-macos-python3.*.zip

print-instructions: vars
	@$(info ┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓)
	@$(info ┃ Next steps:                                               ┃)
	@$(info ┃ 1. Double-check https://github.com/@$(repo)/releases )
	@$(info ┃ 2. Wait a few seconds to let web services do their work   ┃)
	@$(info ┃ 3. Run "make update-doi" to update the DOI in README.md   ┃)
	@$(info ┃ 4. Run "make binaries" to create binaries                 ┃)
	@$(info ┃ 5. Run "make upload-binaries" to upload to Github         ┃)
	@$(info ┃ 6. Run "make packages" and check the results for problems ┃)
	@$(info ┃ 7. Run "make test-pypi" to push to test.pypi.org          ┃)
	@$(info ┃ 8. Double-check https://test.pypi.org/@$(repo) )
	@$(info ┃ 9. Run "make pypi" to push to pypi for real               ┃)
	@$(info ┗━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┛)
	@echo ""

update-doi: vars
	sed -i .bak -e 's|/api/record/[0-9]\{1,\}|/api/record/$(doi_tail)|' README.md
	sed -i .bak -e 's|edu/records/[0-9]\{1,\}|edu/records/$(doi_tail)|' README.md
	sed -i .bak -e '/doi:/ s|10.22002/[0-9]\{1,\}|10.22002/$(doi_tail)|' CITATION.cff
	git add README.md CITATION.cff
	git diff-index --quiet HEAD README.md || \
	    (git commit -m"Update DOI" README.md && git push -v --all)
	git diff-index --quiet HEAD CITATION.cff || \
	    (git commit -m"Update DOI" CITATION.cff && git push -v --all)

packages: | clean
	-mkdir -p $(builddir) $(distdir)
	python3 setup.py sdist --dist-dir $(distdir)
	python3 setup.py bdist_wheel --dist-dir $(distdir)
	python3 -m twine check $(distdir)/$(name)-$(version).tar.gz

# Note: for the next action to work, the repository "testpypi" needs to be
# defined in your ~/.pypirc file. Here is an example file:
#
#  [distutils]
#  index-servers =
#    pypi
#    testpypi
#
#  [testpypi]
#  repository = https://test.pypi.org/legacy/
#  username = YourPyPIlogin
#  password = YourPyPIpassword
#
# You could copy-paste the above to ~/.pypirc, substitute your user name and
# password, and things should work after that. See the following for more info:
# https://packaging.python.org/en/latest/specifications/pypirc/

test-pypi: packages
	python3 -m twine upload --verbose --repository testpypi \
	  $(distdir)/$(name)-$(version)*.{whl,gz}

pypi: packages
	python3 -m twine upload $(distdir)/$(name)-$(version)*.{gz,whl}


# Cleanup and miscellaneous directives ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

clean: clean-dist clean-build clean-release clean-other

really-clean: clean really-clean-dist

clean-dist:
	-rm -fr $(distdir)/$(name) $(distdir)/$(app_name) $(zipfile) \
	    dist/$(name)-$(version)-py3-none-any.whl

really-clean-dist:;
	-rm -fr $(distdir)

clean-build:;
	-rm -rf build/$(os)

clean-release:;
	-rm -rf $(name).egg-info codemeta.json.bak $(initfile).bak README.md.bak

clean-other:;
	-rm -fr __pycache__ $(name)/__pycache__ .eggs

.PHONY: release release-on-github update-init update-codemeta \
	vars print-instructions update-doi packages test-pypi pypi clean \
	clean-dist really-clean-dist clean-build clean-release clean-other
