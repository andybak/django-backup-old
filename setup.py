from setuptools import setup, find_packages

setup(
    name = 'django_backup',
    packages = find_packages(),
    version = '1.0.0',
    description = 'A backup database command for django.',
    author = 'Dmitriy Kovalev',
    #author_email = '',
    url = 'http://github.com/mikexstudios/django-backup',
    classifiers=[
        'Programming Language :: Python', 
        'Framework :: Django', 
        'License :: OSI Approved :: BSD License',
    ]
)

