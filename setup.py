from setuptools import setup

setup(
    name = 'interfacelift-cli',
    version = '0.1',
    install_requires = [
        'requests==2.13.0',
        'beautifulsoup4==4.5.3',
        'PyYAML==3.12'
    ],
    packages = [
        'wallpapers'
    ],
    entry_points = {
        'console_scripts': ['wallpapers = wallpapers.__main__:main']
    }
)
