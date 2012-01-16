from distutils.core import setup

setup(
    name='canon-remote',
    version='0.0.1dev',
    description='Use old Canon cameras with Python',
    long_description=open('README.rst', 'r').read(),
    author='Kiril Zyapkov',
    author_email='kiril.zyapkov@gmail.com',
    url='http://1024.cjb.net',
    license='GPL',
    packages=['canon']
)