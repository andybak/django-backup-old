import os
import time
from tempfile import gettempdir

from django.core.management.base import BaseCommand
from django.conf import settings

import pysftp as ssh

from backup import TIME_FORMAT
from backup import is_db_backup
from backup import is_media_backup

class Command(BaseCommand):
    help = "Restores latest backup."

    def _time_suffix(self):
        return time.strftime(TIME_FORMAT)

    def handle(self, *args, **options):

        from django.db import connection
        from django.conf import settings

        try:
            self.engine = settings.DATABASES['default']['ENGINE']
            self.db = settings.DATABASES['default']['NAME']
            self.user = settings.DATABASES['default']['USER']
            self.passwd = settings.DATABASES['default']['PASSWORD']
            self.host = settings.DATABASES['default']['HOST']
            self.port = settings.DATABASES['default']['PORT']
        except NameError:
            self.engine = settings.DATABASE_ENGINE
            self.db = settings.DATABASE_NAME
            self.user = settings.DATABASE_USER
            self.passwd = settings.DATABASE_PASSWORD
            self.host = settings.DATABASE_HOST
            self.port = settings.DATABASE_PORT


        self.backup_dir = settings.BACKUP_LOCAL_DIRECTORY
        self.remote_dir = settings.RESTORE_FROM_FTP_DIRECTORY
        self.ftp_server = settings.BACKUP_FTP_SERVER
        self.ftp_username = settings.BACKUP_FTP_USERNAME
        self.ftp_password = settings.BACKUP_FTP_PASSWORD

        sftp = self.get_connection()
        backups = [i.strip() for i in sftp.execute('ls %s' % self.remote_dir)]
        db_backups = filter(is_db_backup, backups)
        db_backups.sort()
        media_backups = filter(is_media_backup, backups)
        media_backups.sort()

        tempdir = gettempdir()
        tempdir = settings.PROJECT_DIR

        db_remote = db_backups[-1]
        #media_remote = media_backups[-1]

        db_local = os.path.join(tempdir, db_remote)
        #media_local = os.path.join(tempdir, media_remote)

        sftp.get(os.path.join(self.remote_dir, db_remote), db_local)
        #sftp.get(os.path.join(self.remote_dir, media_remote), media_local)

        self.uncompress(db_local)
        sql_local = db_local[:-3]
        self.mysql_restore(sql_local)


    def get_connection(self):
        '''
        get the ssh connection to the remote server.
        '''
        return ssh.Connection(host = self.ftp_server, username = self.ftp_username, password = self.ftp_password)

    def uncompress(self, file):
        #os.system('tar xvfz %s' % file)
        os.system('gunzip %s' % file)

    def mysql_restore(self, infile):
        args = []
        if self.user:
            args += ["--user=%s" % self.user]
        if self.passwd:
            args += ["--password=%s" % self.passwd]
        if self.host:
            args += ["--host=%s" % self.host]
        if self.port:
            args += ["--port=%s" % self.port]
        args += [self.db]
        cmd = 'mysql %s < %s' % (' '.join(args), infile)
        print cmd
        os.system(cmd)



