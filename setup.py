from setuptools import setup

setup(
    name='interfacelift-cli',
    version='0.2.1',
    author='Ted Tang',
    author_email='s23tang@gmail.com',
    description='Cli tool to download wallapers from Interface Lift',
    url='https://github.com/s23tang/interfacelift-cli-downloader',
    license='MIT',
    install_requires=[
        'requests==2.13.0',
        'beautifulsoup4==4.5.3',
        'PyYAML==3.12'
    ],
    packages=[
        'wallpapers'
    ],
    entry_points={
        'console_scripts': ['interfacelift-cli = wallpapers.__main__:main']
    }
)
