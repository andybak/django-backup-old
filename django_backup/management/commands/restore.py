import os
import time
from optparse import make_option
from tempfile import gettempdir

from django.core.management.base import BaseCommand, CommandError
from django.conf import settings

import pysftp as ssh

from backup import TIME_FORMAT
from backup import is_db_backup
from backup import is_media_backup


class Command(BaseCommand):
    help = "Restores latest backup."
    option_list = BaseCommand.option_list + (
        make_option('--media', '-m', action='store_true', default=False, dest='media',
            help='Restore media dir'),
    )

    def _time_suffix(self):
        return time.strftime(TIME_FORMAT)

    def handle(self, *args, **options):
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
        self.remote_dir = settings.RESTORE_FROM_FTP_DIRECTORY or ''
        self.ftp_server = settings.BACKUP_FTP_SERVER
        self.ftp_username = settings.BACKUP_FTP_USERNAME
        self.ftp_password = settings.BACKUP_FTP_PASSWORD
        self.restore_media = options.get('media')

        print 'Connecting to %s...' % self.ftp_server
        sftp = self.get_connection()
        print 'Connected.'
        backups = [i.strip() for i in sftp.execute('ls %s' % (self.remote_dir))]
        db_backups = filter(is_db_backup, backups)
        db_backups.sort()
        if self.restore_media:
            media_backups = filter(is_media_backup, backups)
            media_backups.sort()

        self.tempdir = gettempdir()

        db_remote = db_backups[-1]
        if self.restore_media:
            media_remote = media_backups[-1]

        db_local = os.path.join(self.tempdir, db_remote)
        print 'Fetching database %s...' % db_remote
        sftp.get(os.path.join(self.remote_dir, db_remote), db_local)
        print 'Uncompressing database...'
        uncompressed = self.uncompress(db_local)
        if uncompressed is 0:
            sql_local = db_local[:-3]
        else:
            sql_local = db_local
        if self.restore_media:
            print 'Fetching media %s...' % media_remote
            media_local = os.path.join(self.tempdir, media_remote)
            sftp.get(os.path.join(self.remote_dir, media_remote), media_local)
            print 'Uncompressing media...'
            self.uncompress_media(media_local)
        # Doing restore
        if self.engine == 'django.db.backends.mysql':
            print 'Doing Mysql restore to database %s from %s...' % (self.db, sql_local)
            self.mysql_restore(sql_local)
        # TODO reinstate postgres support
        elif self.engine == 'django.db.backends.postgresql_psycopg2':
            print 'Doing Postgresql restore to database %s from %s...' % (self.db, sql_local)
            self.posgresql_restore(sql_local)
        else:
            raise CommandError('Backup in %s engine not implemented' % self.engine)

    def get_connection(self):
        '''
        get the ssh connection to the remote server.
        '''
        return ssh.Connection(host=self.ftp_server, username=self.ftp_username, password=self.ftp_password)

    def uncompress(self, file):
        cmd = 'cd %s;gzip -df %s' % (self.tempdir, file)
        print '\t', cmd
        return os.system(cmd)

    def uncompress_media(self, file):
        cmd = u'tar -C %s -xzf %s' % (settings.MEDIA_ROOT, file)
        print u'\t', cmd
        os.system(cmd)

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
        print '\t', cmd
        os.system(cmd)

    def posgresql_restore(self, infile):
        args = ['psql']
        if self.user:
            args.append("-U %s" % self.user)
        if self.passwd:
            os.environ['PGPASSWORD'] = self.passwd
        if self.host:
            args.append("-h %s" % self.host)
        if self.port:
            args.append("-p %s" % self.port)
        args.append('-f %s' % infile)
        args.append("-o %s" % os.path.join(self.tempdir, 'dump.log'))
        args.append(self.db)
        cmd = ' '.join(args)
        print '\t', cmd
        os.system(cmd)
