from setuptools import setup, find_packages

setup(
    name = 'django_backup',
    packages = find_packages(),
    version = '1.0.1',
    description = 'A fork and extension of Dmitriy Kovalev\'s backup database command for django.',
    author = 'Dmitriy Kovalev, Michael Huynh, msaelices, Andy Baker, Chen Zhe',
    #author_email = '',
    url = 'http://github.com/andybak/django-backup',
    classifiers=[
        'Programming Language :: Python', 
        'Framework :: Django', 
        'License :: OSI Approved :: BSD License',
    ]
)

