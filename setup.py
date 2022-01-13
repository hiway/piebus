# coding=utf-8
from glob import glob
from os.path import (
    basename,
    splitext
)
from setuptools import (
    setup,
    find_packages,
)

extras_telegram = ['aiogram==2.1']


setup(
    name='piebus',
    version='0.0.1',
    packages=find_packages('src'),
    package_dir={'': 'src'},
    py_modules=[splitext(basename(path))[0] for path in glob('src/*.py')],
    include_package_data=True,

    install_requires=[
        'asgiref==3.1.2',
        'aiofiles==0.4.0',
        'aiogram==2.1',
        'bcrypt==3.1.6',
        'click==7.0',
        'cookiecutter==1.6.0',
        'pillow==9.0.0',
        'lxml==4.3.3',
        'makeweb==0.1.0',
        'markdown==3.1.1',
        'newspaper3k==0.2.8',
        'osmviz==3.1.0',
        'quart==0.9.1',
        'peewee==3.9.5',
        'pysyncobj==0.3.4',
        'smopy==0.0.7',
        'werkzeug==0.15.4',
    ],

    extras_require={
        'telegram': extras_telegram,
    },

    entry_points={
        'console_scripts': [
            'piebus = piebus.cli:main'
        ]
    },
)
