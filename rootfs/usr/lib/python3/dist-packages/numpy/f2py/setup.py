#!/usr/bin/env python
"""
setup.py for installing F2PY

Usage:
   python setup.py install

Copyright 2001-2005 Pearu Peterson all rights reserved,
Pearu Peterson <pearu@cens.ioc.ee>
Permission to use, modify, and distribute this software is given under the
terms of the NumPy License.

NO WARRANTY IS EXPRESSED OR IMPLIED.  USE AT YOUR OWN RISK.
$Revision: 1.32 $
$Date: 2005/01/30 17:22:14 $
Pearu Peterson
"""

__version__ = "$Id: setup.py,v 1.32 2005/01/30 17:22:14 pearu Exp $"

import os
import sys
from distutils.dep_util import newer
from numpy.distutils import log
from numpy.distutils.core import setup
from numpy.distutils.misc_util import Configuration

from __version__ import version

def configuration(parent_package='',top_path=None):
    config = Configuration('f2py', parent_package, top_path)

    config.add_data_dir('docs')
    config.add_data_dir('tests')

    config.add_data_files('src/fortranobject.c',
                          'src/fortranobject.h',
                          'f2py.1'
                          )

    config.make_svn_version_py()

    def generate_f2py_py(build_dir):
        f2py_exe = 'f2py'+sys.version[:3]
        if f2py_exe[-4:]=='.exe':
            f2py_exe = f2py_exe[:-4] + '.py'
        if 'bdist_wininst' in sys.argv and f2py_exe[-3:] != '.py':
            f2py_exe = f2py_exe + '.py'
        target = os.path.join(build_dir,f2py_exe)
        if newer(__file__,target):
            log.info('Creating %s', target)
            f = open(target,'w')
            f.write('''\
#!/usr/bin/env %s
# See http://cens.ioc.ee/projects/f2py2e/
import os, sys
for mode in ["g3-numpy", "2e-numeric", "2e-numarray", "2e-numpy"]:
    try:
        i=sys.argv.index("--"+mode)
        del sys.argv[i]
        break
    except ValueError: pass
os.environ["NO_SCIPY_IMPORT"]="f2py"
if mode=="g3-numpy":
    sys.stderr.write("G3 f2py support is not implemented, yet.\\n")
    sys.exit(1)
elif mode=="2e-numeric":
    from f2py2e import main
elif mode=="2e-numarray":
    sys.argv.append("-DNUMARRAY")
    from f2py2e import main
elif mode=="2e-numpy":
    from numpy.f2py import main
else:
    sys.stderr.write("Unknown mode: " + repr(mode) + "\\n")
    sys.exit(1)
main()
'''%(os.path.basename(sys.executable)))
            f.close()
        return target

    config.add_scripts(generate_f2py_py)

    log.info('F2PY Version %s', config.get_version())

    return config

if __name__ == "__main__":

    config = configuration(top_path='')
    version = config.get_version()
    print(('F2PY Version',version))
    config = config.todict()

    if sys.version[:3]>='2.3':
        config['download_url'] = "http://cens.ioc.ee/projects/f2py2e/2.x"\
                                 "/F2PY-2-latest.tar.gz"
        config['classifiers'] = [
            'Development Status :: 5 - Production/Stable',
            'Intended Audience :: Developers',
            'Intended Audience :: Science/Research',
            'License :: OSI Approved :: NumPy License',
            'Natural Language :: English',
            'Operating System :: OS Independent',
            'Programming Language :: C',
            'Programming Language :: Fortran',
            'Programming Language :: Python',
            'Topic :: Scientific/Engineering',
            'Topic :: Software Development :: Code Generators',
            ]
    setup(version=version,
          description       = "F2PY - Fortran to Python Interface Generaton",
          author            = "Pearu Peterson",
          author_email      = "pearu@cens.ioc.ee",
          maintainer        = "Pearu Peterson",
          maintainer_email  = "pearu@cens.ioc.ee",
          license           = "BSD",
          platforms         = "Unix, Windows (mingw|cygwin), Mac OSX",
          long_description  = """\
The Fortran to Python Interface Generator, or F2PY for short, is a
command line tool (f2py) for generating Python C/API modules for
wrapping Fortran 77/90/95 subroutines, accessing common blocks from
Python, and calling Python functions from Fortran (call-backs).
Interfacing subroutines/data from Fortran 90/95 modules is supported.""",
          url               = "http://cens.ioc.ee/projects/f2py2e/",
          keywords          = ['Fortran','f2py'],
          **config)
