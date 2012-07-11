django-backup
=============
http://github.com/andybak/django-backup

Backup, compress and restore database and media files. Transfer them via email or FTP and maintain a set number of dated versions on remote FTP server.

Requirements
------------

My fork of Pysftp: https://github.com/andybak/Pysftp
(a nice friendly wrapper around Paramiko: https://github.com/robey/paramiko)

Authors
-------

* project started by Dmitriy Kovalev (http://code.google.com/p/django-backup/ http://code.google.com/u/dmitriy.kovalev/)
* based off of backupdb command by msaelices (http://www.djangosnippets.org/snippets/823/)
* and also snippets from http://www.yashh.com/blog/2008/sep/05/django-database-backup-view/
* with minor modifications by Michael Huynh (mike@mikexstudios.com) http://github.com/mikexstudios/django-backup
* Major modifications in this fork by Andy Baker (andy@andybak.net and Chen Zhe (fruitschen@gmail.com)


New Features in this fork
-------------------------

- Facility to backup media directories in addition to backing up SQL dump
- Transfer backups to remote FTP site
- cleanmedia and cleandb options allow you to only retain a set number of backups on the remote ftp site. Can specify via settings different values for days, weeks and years to retain (see below)
- 'manage.py restore' pulls down the latest backup from FTP and feeds it to mysql
- option to delete alllocal backups
- if using FTP you can opt not to retain local copy of backups
- Unfortunately Postgres support hasn't been kept up to date in this version. It shouldn't be that hard to replace.


Supported options for manage.py backup
--------------------------------------
::
    --email
    default=None
    Sends email with attached dump file

    --compress -c
    default=False
    Compress SQL dump file

    --ftp -f
    default=False
    Store backup on remote FTP server

    --media -m
    default=False
    Backup media dirs as well as SQL dump

    --nolocal
    default=False
    Keep local copies of backup

    --deletelocal
    default=False
    Delete all local backups

    --cleandb
    default=False
    Clean up surplus database backups

    --cleanmedia
    default=False
    Clean up surplus media backups

    --cleanlocaldb
    default=False
    Clean up surplus local database backups

    --cleanlocalmedia
    default=False
    Clean up surplus local media backups

    --cleanremotedb
    default=False
    Clean up surplus remote database backups

    --cleanremotemedia
    default=False
    Clean up surplus remote media backups

Extra Settings
--------------
::
  BACKUP_SQLDUMP_PATH = '/path/to/mysqldump' # mysqldump binary location
  BACKUP_LOCAL_DIRECTORY = '/path/to/backups' # Where to store local backups

  BACKUP_FTP_SERVER = 'example.com'
  BACKUP_FTP_USERNAME = 'username'
  BACKUP_FTP_PASSWORD = 'password'
  BACKUP_FTP_DIRECTORY = '/path/to/backups/mysite' # If you store multiple backups on the same remote server ensure each one is in a different directory
  RESTORE_FROM_FTP_DIRECTORY = '/path/to/backups/mysite' # Where does the restore

  # How many db backups should we keep on remote FTP? i.e. 1 per day for the last 7 days plus 1 per week for the last 4 weeks etc.
  BACKUP_DATABASE_COPIES = {
     'daily': 7,
     'weekly': 4,
     'monthly': 12,
  }

  # Same as above
  BACKUP_MEDIA_COPIES = {
     'daily': 1,
     'weekly': 2,
     'monthly': 4,
  }
