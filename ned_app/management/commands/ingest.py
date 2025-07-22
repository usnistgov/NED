from django.core.management.base import BaseCommand
from ned_app.serialization.data_files_processor import import_avail_data
from ned_app.serialization.custom_exceptions import DataFileLoadError, DataFileDeserializationError

class Command(BaseCommand):
    help = 'Ingests data from any available JSON data files and inserts them into the database'

    def handle(self, *args, **options):
        try:
            import_avail_data()

            print("success!")

        except DataFileLoadError as ex:
            err_msg = (f"A '{ex.__class__.__name__}' exception was trapped while trying to digest data. Message: {ex}")
            print(err_msg)
        except DataFileDeserializationError as ex:
            err_msg = (f"A '{ex.__class__.__name__}' exception was trapped while trying to digest data. Message: {ex}")
            print(err_msg)