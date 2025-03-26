from django.core.management.base import BaseCommand, CommandParser
from ned.models import References

stdChoices = [std[0] for std in References.studytypeChoices.choices]

class Command(BaseCommand):
    help = "A command to add one new row of data to the references db"

    def add_arguments(self, parser: CommandParser):
        parser.add_argument("name", type=str, 
                            help="Title of the study")
        parser.add_argument("author", type=str, 
                            help="Last name of the primary author")
        parser.add_argument("year", type=int, 
                            help="The year the study was published")
        parser.add_argument("study_type", type=str, choices=stdChoices, 
                            help="Choose type of study")
        parser.add_argument("--comp_type", type=str, default="", 
                            help="Type of component under investigations")
        parser.add_argument("--doi", type=str, 
                            help="Digital Object Identifier")
        parser.add_argument("--citation", type=str, default="", 
                            help="Full text based citition of publication")
        parser.add_argument("--publication_type", type=str, default="", 
                            help="Choose the type of publication")
        parser.add_argument("--pdf_saved", type=bool, default=False,
                            help="True if the PDF is saved in the DB")
    
    def handle(self, *args, **options):
        References.objects.create(name=options["name"], 
                                  author=options["author"], 
                                  year=options["year"], 
                                  study_type=options["study_type"], 
                                  comp_type=options["comp_type"], 
                                  doi=options["doi"], 
                                  citation=options["citation"], 
                                  publication_type=options["publication_type"], 
                                  pdf_saved=options["pdf_saved"]
                                  )
        print("Added " + options["name"] + "to References DB")