import pandas as pd
from django.core.management.base import BaseCommand, CommandParser
from ned.models import *
from sqlalchemy import create_engine

class Command(BaseCommand):
    help = "A command to add data from a csv file to the database"

    def add_arguments(self, parser: CommandParser):
        parser.add_argument("db_filename", type=str, help="this is the name of the file that you want to initialize data from")

        parser.add_argument("db_model", type=str, help="this is a test string to print")
    
    def handle(self, *args, **options):
        db_filename = options["db_filename"]
        db_model = options["db_model"]

        print("Initializing data from " + db_filename + " into " + db_model + " SQL database")

        # Pull in csv data
        df = pd.read_csv(db_filename)
        #print(df)
        
        # Get the dynamic db model name from the global namespace
        class_object = globals()[db_model]
        print(class_object)
  
        # Append data to SQL schema (defined by Django Model)
        engine = create_engine('sqlite:///db.sqlite3')
        df.to_sql(class_object._meta.db_table, if_exists='append', con=engine, index=False)