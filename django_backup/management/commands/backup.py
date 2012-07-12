import calendar
import os
import popen2
import time
from datetime import datetime
from datetime import timedelta
from optparse import make_option
import re

from django.core.management.base import BaseCommand, CommandError
from django.core.mail import EmailMessage
from django.conf import settings

import pysftp as ssh

TIME_FORMAT = '%Y%m%d-%H%M%S'
regex = re.compile(r'(\d){8}-(\d){6}')

def is_db_backup(filename):
    return filename.startswith('backup_')

def is_media_backup(filename):
    return filename.startswith('dir_')

def is_backup(filename):
    return (is_db_backup(filename) or is_media_backup(filename))

def get_date(filename):
    '''
    given the name of the backup file, return the datetime it was created.
    '''
    result = regex.search(filename)
    date_str = result.group()
    d = datetime.strptime(date_str, TIME_FORMAT)
    return d

def between_interval(filename, start, end):
    '''
    given a filename and an interval, tell if it's between the interval
    '''
    d = get_date(filename)
    #print start, filename, end
    if d > start and d <= end:
        return True
    else:
        return False

def reserve_interval(backups, type, num):
    '''
    given a list of backup filenames, interval type(monthly, weekly, daily),
    and the number of backups to keep, return a list of filenames to reserve.
    '''
    result = []
    now = datetime.now()
    if type == 'monthly':
        delta = timedelta(30)
        interval_end = datetime(now.year, now.month, 1) # begin of the month
        interval_start = interval_end - delta
    elif type == 'weekly':
        delta = timedelta(7)
        weekday = calendar.weekday(now.year, now.month, now.day)
        weekday_delta = timedelta(weekday)
        interval_end = datetime(now.year, now.month, now.day) - weekday_delta # begin of the week
        interval_start = interval_end - delta
    elif type == 'daily':
        delta = timedelta(1)
        interval_end = datetime(now.year, now.month, now.day) + delta
        interval_start = interval_end - delta
    for i in range(1,num+1):
        for backup in backups:
            if between_interval(backup,interval_start,interval_end):
                result.append(backup)
                break # reserve only one backup per interval
        interval_end = interval_end - delta
        interval_start = interval_start - delta
    return result

def decide_remove(backups, config):
    '''
    given a list of backup filenames and setttings, decide the files to be deleted.
    '''
    reserve = []
    remove_list = []
    reserve += reserve_interval(backups, 'monthly' ,config['monthly'])
    reserve += reserve_interval(backups, 'weekly', config['weekly'])
    reserve += reserve_interval(backups, 'daily', config['daily'])
    for i in backups:
        if i not in reserve:
            remove_list.append(i)
    return remove_list

# Based on: http://www.djangosnippets.org/snippets/823/
# Based on: http://www.yashh.com/blog/2008/sep/05/django-database-backup-view/
class Command(BaseCommand):
    option_list = BaseCommand.option_list + (
        make_option('--email', default=None, dest='email',
            help='Sends email with attached dump file'),
        make_option('--ftp', '-f', action='store_true', default=False, dest='ftp',
            help='Backup file via FTP'),
        make_option('--compress', '-c', action='store_true', default=False, dest='compress',
            help='Compress dump file'),
        make_option('--directory', '-d', action='append', default=[], dest='directories',
            help='Destination Directory'),
        make_option('--media', '-m', action='store_true', default=False, dest='media',
            help='Backup media dir'),
        make_option('--cleandb', action='store_true', default=False, dest='clean_db',
            help='Clean up surplus database backups'),
        make_option('--cleanmedia', action='store_true', default=False, dest='clean_media',
            help='Clean up surplus media backups'),
        make_option('--nolocal', action='store_true', default=False, dest='no_local',
            help='Reserve local backup or not'),
        make_option('--deletelocal', action='store_true', default=False, dest='delete_local',
            help='Delete all local backups'),
        make_option('--cleanlocaldb', action='store_true', default=False, dest='clean_local_db',
            help='Clean up surplus local database backups'),
        make_option('--cleanremotedb', action='store_true', default=False, dest='clean_remote_db',
            help='Clean up surplus remote database backups'),
        make_option('--cleanlocalmedia', action='store_true', default=False, dest='clean_local_media',
            help='Clean up surplus local media backups'),
        make_option('--cleanremotemedia', action='store_true', default=False, dest='clean_remote_media',
            help='Clean up surplus remote media backups'),
    )
    help = "Backup database. Only Mysql and Postgresql engines are implemented"

    def _time_suffix(self):
        return time.strftime(TIME_FORMAT)

    def handle(self, *args, **options):
        self.email = options.get('email')
        self.ftp = options.get('ftp')
        self.compress = options.get('compress')
        self.directories = options.get('directories')
        self.media = options.get('media')
        self.clean = options.get('clean')
        self.clean_db = options.get('clean_db')
        self.clean_media = options.get('clean_media')
        self.clean_local_db = options.get('clean_local_db')
        self.clean_remote_db = options.get('clean_remote_db')
        self.clean_local_media = options.get('clean_local_media')
        self.clean_remote_media = options.get('clean_remote_media')
        self.no_local = options.get('no_local')
        self.delete_local = options.get('delete_local')

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
        self.remote_dir = settings.BACKUP_FTP_DIRECTORY
        self.ftp_server = settings.BACKUP_FTP_SERVER
        self.ftp_username = settings.BACKUP_FTP_USERNAME
        self.ftp_password = settings.BACKUP_FTP_PASSWORD

        if self.clean_db:
            print 'cleaning surplus database backups'
            self.clean_surplus_db()

        if self.clean_local_db:
            print 'cleaning local surplus database backups'
            self.clean_local_surplus_db()

        if self.clean_remote_db:
            print 'cleaning remote surplus database backups'
            self.clean_remote_surplus_db()

        if self.clean_media:
            print 'cleaning surplus media backups'
            self.clean_surplus_media()

        if self.clean_local_media:
            print 'cleaning local surplus media backups'
            self.clean_local_surplus_media()

        if self.clean_remote_media:
            print 'cleaning remote surplus media backups'
            self.clean_remote_surplus_media()

        if not os.path.exists(self.backup_dir):
            os.makedirs(self.backup_dir)

        outfile = os.path.join(self.backup_dir, 'backup_%s.sql' % self._time_suffix())

        # Doing backup
        if self.engine == 'django.db.backends.mysql':
            print 'Doing Mysql backup to database %s into %s' % (self.db, outfile)
            self.do_mysql_backup(outfile)
        # TODO reinstate postgres support
        #elif self.engine in ('postgresql_psycopg2', 'postgresql'):
        #    print 'Doing Postgresql backup to database %s into %s' % (self.db, outfile)
        #    self.do_postgresql_backup(outfile)
        else:
            raise CommandError('Backup in %s engine not implemented' % self.engine)

        # Compressing backup
        if self.compress:
            compressed_outfile = outfile + '.gz'
            print 'Compressing backup file %s to %s' % (outfile, compressed_outfile)
            self.do_compress(outfile, compressed_outfile)
            outfile = compressed_outfile

        # Backing up media directories,
        if self.media:
            self.directories += [settings.MEDIA_ROOT]

        # Backing up directories
        dir_outfiles = []

        # Backup all the directories in one file. 
        if self.directories:
            all_directories = ' '.join(self.directories)
            all_outfile = os.path.join(self.backup_dir, 'dir_%s.tar.gz' % (self._time_suffix()))
            self.compress_dir(all_directories, all_outfile)
            dir_outfiles.append(all_outfile)

        # Sending mail with backups
        if self.email:
            print "Sending e-mail with backups to '%s'" % self.email
            self.sendmail(settings.SERVER_EMAIL, [self.email], dir_outfiles + [outfile])

        if self.ftp:
            print "Saving to remote server"
            self.store_ftp(local_files=[os.path.join(os.getcwd(),x) for x in dir_outfiles + [outfile]])

    def compress_dir(self, directory, outfile):
        print 'Backup directories ...'
        command = 'tar -czf %s %s' % (outfile, directory)
        print '=' * 70
        print 'Running Command: %s' % command
        os.system(command)
        
    def get_connection(self):
        '''
        get the ssh connection to the remote server.
        '''
        return ssh.Connection(host = self.ftp_server, username = self.ftp_username, password = self.ftp_password)
        
    def store_ftp(self, local_files=[]):
        sftp = self.get_connection()
        try:
            sftp.mkdir(self.remote_dir)
        except IOError:
            pass
        for local_file in local_files:
            filename = os.path.split(local_file)[-1]
            print 'Saving %s to remote server ' % local_file
            sftp.put(local_file, os.path.join(self.remote_dir,filename))
        sftp.close()
        if self.delete_local:
            backups = os.listdir(self.backup_dir)
            backups = filter(is_backup, backups)
            backups.sort()
            print '=' * 70
            print '--cleanlocal, local db and media backups found: %s' % backups
            remove_list = backups
            print 'local db and media backups to clean %s' % remove_list
            remove_all = ' '.join([os.path.join(self.backup_dir,i) for i in remove_list])
            if remove_all:
                print '=' * 70
                print 'cleaning up local db and media backups'
                command = 'rm %s' % remove_all
                print '=' * 70
                print 'Running Command: %s' % command
                os.system(command)
            # remote(ftp server)
        elif self.no_local:
            to_remove = local_files
            print '=' * 70
            print '--nolocal, Local files to remove %s' % to_remove
            remove_all = ' '.join(to_remove)
            if remove_all:
                print '=' * 70
                print 'cleaning up local backups'
                command = 'rm %s' % remove_all
                print '=' * 70
                print 'Running Command: %s' % command
                os.system(command)
        
    def sendmail(self, address_from, addresses_to, attachments):
        subject = "Your DB-backup for " + datetime.now().strftime("%d %b %Y")
        body = "Timestamp of the backup is " + datetime.now().strftime("%d %b %Y")

        email = EmailMessage(subject, body, address_from, addresses_to)
        email.content_subtype = 'html'
        for attachment in attachments:
            email.attach_file(attachment)
        email.send()

    def do_compress(self, infile, outfile):
        os.system('gzip --stdout %s > %s' % (infile, outfile))
        os.system('rm %s' % infile)

    def do_mysql_backup(self, outfile):
        args = []
        if self.user:
            args += ["--user='%s'" % self.user]
        if self.passwd:
            args += ["--password='%s'" % self.passwd]
        if self.host:
            args += ["--host='%s'" % self.host]
        if self.port:
            args += ["--port=%s" % self.port]
        args += [self.db]
        os.system('%s %s > %s' % (getattr(settings, 'BACKUP_SQLDUMP_PATH', 'mysqldump'), ' '.join(args), outfile))

    def do_postgresql_backup(self, outfile):
        args = []
        if self.user:
            args += ["--username=%s" % self.user]
        if self.passwd:
            args += ["--password"]
        if self.host:
            args += ["--host=%s" % self.host]
        if self.port:
            args += ["--port=%s" % self.port]
        if self.db:
            args += [self.db]
        pipe = popen2.Popen4('pg_dump %s > %s' % (' '.join(args), outfile))
        if self.passwd:
            pipe.tochild.write('%s\n' % self.passwd)
            pipe.tochild.close()

    def clean_local_surplus_db(self):
        try:
            backups = os.listdir(self.backup_dir)
            backups = filter(is_db_backup, backups)
            backups.sort()
            print '=' * 70
            print 'local db backups found: %s' % backups
            remove_list = decide_remove(backups, settings.BACKUP_DATABASE_COPIES)
            print '=' * 70
            print 'local db backups to clean %s' % remove_list
            remove_all = ' '.join([os.path.join(self.backup_dir,i) for i in remove_list])
            if remove_all:
                print '=' * 70
                print 'cleaning up local db backups'
                command = 'rm %s' % remove_all
                print '=' * 70
                print 'Running Command: %s' % command
                os.system(command)
        except ImportError:
            print 'cleaned nothing, because BACKUP_DATABASE_COPIES is missing'

    def clean_remote_surplus_db(self):
        try:
            sftp = self.get_connection()
            backups = [i.strip() for i in sftp.execute('ls %s' % self.remote_dir)]
            backups = filter(is_db_backup, backups)
            backups.sort()
            print '=' * 70
            print 'remote db backups found: %s' % backups
            remove_list = decide_remove(backups, settings.BACKUP_DATABASE_COPIES)
            print '=' * 70
            print 'remote db backups to clean %s' % remove_list
            remove_all_remote = ' '.join([os.path.join(self.remote_dir,i) for i in remove_list])
            if remove_all_remote:
                print '=' * 70
                print 'cleaning up remote db backups'
                command = 'rm %s' % remove_all_remote
                print '=' * 70
                print 'Running Command on remote server: %s' % command
                sftp.execute(command)
            sftp.close()
        except ImportError:
            print 'cleaned nothing, because BACKUP_DATABASE_COPIES is missing'


    def clean_surplus_db(self):
        self.clean_local_surplus_db()
        self.clean_remote_surplus_db()


    def clean_surplus_media(self):
        self.clean_local_surplus_media()
        self.clean_remote_surplus_media()

    def clean_local_surplus_media(self):
        try:
            # local(web server)
            backups = os.listdir(self.backup_dir)
            backups = filter(is_media_backup, backups)
            backups.sort()
            print '=' * 70
            print 'local media backups found: %s' % backups
            remove_list = decide_remove(backups, settings.BACKUP_MEDIA_COPIES)
            print '=' * 70
            print 'local media backups to clean %s' % remove_list
            remove_all = ' '.join([os.path.join(self.backup_dir,i) for i in remove_list])
            if remove_all:
                print '=' * 70
                print 'cleaning up local media backups'
                command = 'rm %s' % remove_all
                print '=' * 70
                print 'Running Command: %s' % command
                os.system(command)
        except ImportError:
            print 'cleaned nothing, because BACKUP_MEDIA_COPIES is missing'

    def clean_remote_surplus_media(self):
        try:
            sftp = self.get_connection()
            backups = [i.strip() for i in sftp.execute('ls %s' % self.remote_dir)]
            backups = filter(is_media_backup, backups)
            backups.sort()
            print '=' * 70
            print 'remote media backups found: %s' % backups
            remove_list = decide_remove(backups, settings.BACKUP_MEDIA_COPIES)
            print '=' * 70
            print 'remote media backups to clean %s' % remove_list
            remove_all_remote = ' '.join([os.path.join(self.remote_dir,i) for i in remove_list])
            if remove_all_remote:
                print '=' * 70
                print 'cleaning up remote media backups'
                command = 'rm %s' % remove_all_remote
                print '=' * 70
                print 'Running Command on remote server: %s' % command
                sftp.execute(command)
            sftp.close()
        except ImportError:
            print 'cleaned nothing, because BACKUP_MEDIA_COPIES is missing'


