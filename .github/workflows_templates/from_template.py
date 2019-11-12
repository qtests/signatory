# Copyright 2019 Patrick Kidger. All Rights Reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
# =========================================================================
"""This file generates GitHub Actions from templates.

The template system is pretty simple at the moment. That's probably for the best!

Each action has three things it must specify:
    event_name - this is the name of the event that normally triggers the action.
    event_cond - this is a condition that must be satisfied when the action is triggered via event_name
    trigger - this is the name of the action as used with repository_dispatch

These are specified as arguments in the template file, as a file e,g,
"""


import io
import os
import re


# We don't use the normal Python {} syntax for substitution because GitHub already have a similar syntax for
# substitution, and wires risk getting crossed.
# Admittedly it would probably make more sense to use a pre-built template engine.
def _substitute(filename, **subs):
    """Reads a file with name `filename`.template and creates a file called `filename` by substituting substitutions of
    the form `<<example>>`.
    
    e.g. if subs={'example': 'some text'} then '<<example>>' will become 'some text'.
    
    It's smart enough to add enough white space to every new extra line of the substituted text, to match the
    indentation of the substitution point.
    """

    print('Started templating', filename)

    here = os.path.realpath(os.path.dirname(__file__))

    with io.open(os.path.join(here, filename + '.template'), encoding='utf-8', mode='r') as f:
        template_lines = f.readlines()

    print('Finding arguments')
    # Look for the header of the form:
    # # Arguments:
    # Then take every line after that that looks like it's specifying an argument.
    argument_header_finder = re.compile('^ *# *Arguments: *$')
    argument_finder = re.compile(r'^ *# *([-\w]+): *([-\.\w]+) *(#.*)?$')
    found_argument_header = False
    for line in template_lines:
        if argument_header_finder.match(line):
            found_argument_header = True
            continue
        if found_argument_header:
            argument_match = argument_finder.match(line)
            if argument_match is None:
                break  # found all arguments
            argument_name = argument_match.group(1)
            argument_value = argument_match.group(2)
            print('Found', argument_name, 'with value', argument_value)
            if argument_name in subs:
                raise RuntimeError('Argument {} already in subs for filename {}'.format(argument_name, filename))
            subs[argument_name] = argument_value
    print('Finished finding arguments')
    template = ''.join(template_lines)
    del template_lines

    # Compile regular expressions for each substitution
    subs_re = {}
    for sub_key, sub_val_raw in subs.items():
        sub_key_bracket = '<<{}>>'.format(sub_key)
        sub_re = re.compile(r'^.*{}'.format(sub_key_bracket), flags=re.MULTILINE)
        sub_val_split = sub_val_raw.split('\n')
        subs_re[sub_key_bracket] = (sub_re, sub_val_split)

    while True:
        found = False
        for sub_key_bracket, (sub_re, sub_val_split) in subs_re.items():
            searched = sub_re.search(template)
            if not searched:
                continue
            found = True
            white_space_amount = searched.end() - searched.start() - len(sub_key_bracket)
            white_space = ' ' * white_space_amount
            # We actually replace the <<tag>> and all of the text preceding it on the line; it's just that we copy all
            # of the preceding text back as-is.
            # (Would also be fine to leave the preceding text alone, but this is slightly easier to code.)
            first_characters = template[searched.start():searched.start() + white_space_amount]
            white_sub_vals = [first_characters + sub_val_split[0]]
            white_sub_vals.extend([white_space + sub_val for sub_val in sub_val_split[1:]])
            template = template[:searched.start()] + '\n'.join(white_sub_vals) + template[searched.end():]
        if not found:
            break

    unsubbed = re.compile(r'<<\w*>>')
    search = unsubbed.search(template)
    if search:
        raise RuntimeError('Found unsubbed string {} in {}'.format(search.group(), filename))

    template = '\n'.join(['################################################',
                          '###                                          ###',
                          '### THIS FILE IS AUTOGENERATED. DO NOT EDIT. ###',
                          '###                                          ###',
                          '################################################',
                          '',
                          template])
    with io.open(os.path.join(here, '..', 'workflows', filename), encoding='utf-8', mode='w') as f:
        f.write(template)

    print('Finished templating', filename)


# These are some common strings to substitute in
global_subs = dict(

# Names of operating systems as GitHub Actions specifies them
windows = "windows-2016",
linux = "ubuntu-16.04",
mac = "macOS-10.14",

# Run on repository_dispatch and precisely one other event
on = \
"""on:
  repository_dispatch:
  <<event_name>>:""",

# Only run on repository_dispatch
on_rd = "on: repository_dispatch",

# Versions of Python
# Note that it's actually important to specify the patch number here as well for maximum compatibility.
# (e.g. 3.6.6 vs 3.6.9 does break things)
py27 = '2.7.13',
py35 = '3.5.4',
py36 = '3.6.2',
py37 = '3.7.0',

# Versions of PyTorch
pytorch12 = '1.2.0',
pytorch13 = '1.3.0',
pytorch_all = '[<<pytorch12>>, <<pytorch13>>]',

# A strategy for every operating system and version of Python
# Note that every possible combination must be specified in action_os and action_pv to have repository_dispatch work
# correctly
strategy = \
"""runs-on: ${{ matrix.os }}
strategy:
  matrix:
    os: [<<windows>>, <<linux>>, <<mac>>]
    python-version: [<<py27>>, <<py35>>, <<py36>>, <<py37>>]
    pytorch-version: <<pytorch_all>>
    exclude:
      # PyTorch doesn't support this combination
      - os: <<windows>>
        python-version: <<py27>>
  fail-fast: false""",

# A single Linux strategy
strategy_single = \
"""runs-on: ${{ matrix.os }}
strategy:
  matrix:
    os: [<<linux>>]
    python-version: [<<py37>>]
    pytorch-version: [<<pytorch12>>]
""",

# A single Linux strategy except with all PyTorch versions
strategy_single_all_pytorch = \
"""runs-on: ${{ matrix.os }}
strategy:
  matrix:
    os: [<<linux>>]
    python-version: [<<py37>>]
    pytorch-version: <<pytorch_all>>
""",

# Tests whether a repository_dispatch-triggered action is triggered at all
# Note that trigger is intended to have a space after it (used to distinguish similar triggers)
action_trigger = "contains(github.event.action, '-trigger <<trigger>> ')",

# Tests whether a repository_dispatch-triggered action is triggered, depending on operating system
# Yes, this is a little mad. Only way I could get it work though. It seems like things like matrix.os
# only resolve into strings under certain circumstances.
_action_os_windows = "(contains(github.event.action, '-os <<windows>>') && matrix.os == '<<windows>>')",
_action_os_linux = "(contains(github.event.action, '-os <<linux>>') && matrix.os == '<<linux>>')",
_action_os_mac = "(contains(github.event.action, '-os <<mac>>') && matrix.os == '<<mac>>')",
_action_os_star = "contains(github.event.action, '-os *')",
action_os = "(<<_action_os_windows>> || <<_action_os_linux>> || <<_action_os_mac>> || <<_action_os_star>>)",

# Tests whether a repository_dispatch-triggered action is triggered, depending on Python version
_action_pv_27 = "(contains(github.event.action, '-pv <<py27>>') && matrix.python-version == '<<py27>>')",
_action_pv_35 = "(contains(github.event.action, '-pv <<py35>>') && matrix.python-version == '<<py35>>')",
_action_pv_36 = "(contains(github.event.action, '-pv <<py36>>') && matrix.python-version == '<<py36>>')",
_action_pv_37 = "(contains(github.event.action, '-pv <<py37>>') && matrix.python-version == '<<py37>>')",
_action_pv_star = "contains(github.event.action, '-pv *')",
action_pv = "(<<_action_pv_27>> || <<_action_pv_35>> || <<_action_pv_36>> || <<_action_pv_37>> || <<_action_pv_star>>)",

# Tests whether a step is triggered via the normal event associated with the workflow
if_event = "(github.event_name == '<<event_name>>' && (<<event_cond>>))",

# Tests whether a step is triggered via repository_dispatch
if_repository_dispatch = "(github.event_name == 'repository_dispatch' && <<action_trigger>> && <<action_os>> && <<action_pv>>)",

# A generic if statement that should be on every step
# Will trigger the step if the normal event_name is the reason the workflow is running, and the event_cond is met
# OR
# if repository_dispatch is the reason the workflow is running, and the trigger, os, and Python version all match
if_ = "if: (<<if_event>> || <<if_repository_dispatch>>)",


# A step to checkout Code
checkout_code = \
"""name: Checkout code
<<if_>>
uses: actions/checkout@v1""",

# A step to install Python 3.7. NOTE THAT IT IS DELIBERATELY ONLY 3.7.
# For other versions of Python then please use conda.
# The reason for this is that the setup-python action does not support many of the possible patch versions of Python.
install_python= \
"""name: Install Python
<<if_>>
uses: actions/setup-python@v1
with:
  python-version: '3.7'""",

# Performs the necessary set-up for Windows.
setup_windows = \
r"""name: Windows
<<if_>> && (matrix.os == '<<windows>>')
env:
  PYTHON_VERSION: ${{ matrix.python-version }}
shell: cmd
# && chaining seems to be the best (only?) way to run multiple commands in a cmd shell
# It also means that if any command fails then the step as a whole should correctly
# have a nonzero (fail) return code
run: >
  "C:/Program Files (x86)/Microsoft Visual Studio/2017/Enterprise/VC/Auxiliary/Build/vcvars64.bat" &&
  %CONDA%/Scripts/conda create -n myenv python=%PYTHON_VERSION% -y &&
  %CONDA%/Scripts/activate myenv &&
  python -m pip install --upgrade pip &&
  conda install pytorch==${{ matrix.pytorch-version }} -c pytorch -y &&
  python command.py should_not_import &&""",

# Builds a bdist_wheel on Windows
build_windows = '  python setup.py egg_info --tag-build=".torch${{ matrix.pytorch-version }}" bdist_wheel &&',

# Install from sdist or bdist_wheel on Windows
install_local_windows = '  for %%f in (./dist/*) do (python -m pip install ./dist/%%~nxf) &&',

# Install from PyPI on Windows
install_remote_windows = \
"""  python -c "import subprocess;
  import sys;
  import time;
  import metadata;
  sleep = lambda t: time.sleep(t) or True;
  retry = lambda fn: fn() or (sleep(20) and fn()) or (sleep(40) and fn()) or (sleep(120) and fn()) or (sleep(240) and fn());
  ret = retry(lambda: not subprocess.run('python -m pip install signatory==' + metadata.version + '.torch${{ matrix.pytorch-version }} --only-binary signatory').returncode);
  sys.exit(not ret)
  " &&""",

# Runs tests on Windows
test_windows = \
r"""  python -m pip install iisignature pytest &&
  python -c "import os;
  import subprocess;
  import sys;
  print(sys.version);
  returncode_test = subprocess.Popen('python command.py test', shell=True).wait();
  returncode_version = sys.version[:5] != os.environ['PYTHON_VERSION'][:5];
  sys.exit(max(returncode_test, returncode_version))
  " &&""",

# Terminates a string of commands on Windows
terminate_windows = "  echo done",

# Performs setup for running on Linux
setup_linux = \
r"""name: Linux
<<if_>> && (matrix.os == '<<linux>>')
env:
  PYTHON_VERSION: ${{ matrix.python-version }}
# Deliberately only creating an sdist; see FAQ
run: |
  set -x
  . $CONDA/etc/profile.d/conda.sh
  conda create -n myenv python=$PYTHON_VERSION -y
  conda activate myenv
  python -m pip install --upgrade pip
  conda install pytorch==${{ matrix.pytorch-version }} -c pytorch -y
  python command.py should_not_import""",

# 'Builds' on Linux
build_linux = '  python setup.py egg_info --tag-build=".torch${{ matrix.pytorch-version }}" sdist',

# Install from sdist or bdist_wheel on Linux
install_local_linux = \
"""  SIGNATORY_INSTALLED=$(python -c \"import os
  import sys
  x = os.listdir('dist')
  print(x[0])
  sys.exit(len(x) != 1)\")
  python -m pip install ./dist/$SIGNATORY_INSTALLED""",

# Install from PyPI on Linux
install_remote_linux = \
"""  retry () { $* || (sleep 20 && $*) || (sleep 40 && $*) || (sleep 120 && $*) || (sleep 240 && $*); }
  SIGNATORY_VERSION=$(python -c "import metadata; print(metadata.version)")
  retry python -m pip install signatory==$SIGNATORY_VERSION.torch${{ matrix.pytorch-version }} --no-binary signatory""",

# Runs tests on Linux
test_linux = \
r"""  python -m pip install iisignature pytest
  python -c "import os
  import subprocess
  import sys
  print(sys.version)
  returncode_test = subprocess.Popen('python command.py test', shell=True).wait()
  returncode_version = sys.version[:5] != os.environ['PYTHON_VERSION'][:5]
  sys.exit(max(returncode_test, returncode_version))
  " """,

# Terminates a string of commands on Linux (not actually necessary,
# but we use it for consistency with the other two OS)
terminate_linux = "",

# Setup for running on Mac. Need to install LLVM to get OpenMP support. Must happen outside the sudo'd file as Homebrew
# can't be run as root.
setup_mac = \
r"""name: Mac
<<if_>> && (matrix.os == '<<mac>>')
env:
  PYTHON_VERSION: ${{ matrix.python-version }}
run: |
  set -x
  brew update
  brew install llvm libomp
  echo 'set -ex
  . $CONDA/etc/profile.d/conda.sh
  conda create -n myenv python=$PYTHON_VERSION -y
  conda activate myenv
  python -m pip install --upgrade pip
  conda install pytorch==${{ matrix.pytorch-version }} -c pytorch -y
  python command.py should_not_import""",

# Builds bdist_wheel on Mac.
build_mac = \
"""  export LDFLAGS="-L/usr/local/opt/llvm/lib -Wl,-rpath,/usr/local/opt/llvm/lib"
  export CPPFLAGS="-I/usr/local/opt/llvm/include"
  MACOSX_DEPLOYMENT_TARGET=10.9 CC=/usr/local/opt/llvm/bin/clang CXX=/usr/local/opt/llvm/bin/clang++ python setup.py egg_info --tag-build=".torch${{ matrix.pytorch-version }}" bdist_wheel""",

# Install from sdist or bdist_wheel on Mac
install_local_mac = \
"""  SIGNATORY_INSTALLED=$(python -c \"import os
  import sys
  x = os.listdir('\\''dist'\\'')
  print(x[0])
  sys.exit(len(x) != 1)\")
  python -m pip install ./dist/$SIGNATORY_INSTALLED""",

# Install from PyPI on Mac
install_remote_mac = \
"""  retry () { $* || (sleep 20 && $*) || (sleep 40 && $*) || (sleep 120 && $*) || (sleep 240 && $*); }
  SIGNATORY_VERSION=$(python -c "import metadata; print(metadata.version)")
  retry python -m pip install signatory==$SIGNATORY_VERSION.torch${{ matrix.pytorch-version }} --only-binary signatory""",

# Runs tests on Mac
test_mac = \
"""  git clone https://github.com/bottler/iisignature.git
  cd iisignature
  python setup.py install
  cd ..
  rm -rf iisignature
  python -m pip install pytest
  python -c "import os
  import subprocess
  import sys
  print(sys.version)
  returncode_test = subprocess.Popen('\\''python command.py test'\\'', shell=True).wait()
  returncode_version = sys.version[:5] != os.environ['\\''PYTHON_VERSION'\\''][:5]
  sys.exit(max(returncode_test, returncode_version))
  " """,

# Terminate a string of commands on Mac
terminate_mac = \
"""  ' > $GITHUB_WORKSPACE/to_run.sh
  chmod +x $GITHUB_WORKSPACE/to_run.sh
  sudo -s -H -E $GITHUB_WORKSPACE/to_run.sh""",

# Uploads dist/* to PyPI for Windows
upload_windows = \
r"""  pip install twine &&
  twine upload -u patrick-kidger -p ${{ secrets.pypi_password }} dist/* &&""",

# Uploads dist/* to PyPI for Unix
upload_unix = \
"""  pip install twine
  twine upload -u patrick-kidger -p ${{ secrets.pypi_password }} dist/*""",
)  # end of global_subs
global_subs['upload_mac'] = global_subs['upload_linux'] = global_subs['upload_unix']


def main():
    """Make all templates."""
    _substitute('build.yml', **global_subs)
    _substitute('deploy.yml', **global_subs)
    _substitute('test_deployed.yml', **global_subs)
    _substitute('log_dispatch.yml', **global_subs)


if __name__ == '__main__':
    main()

