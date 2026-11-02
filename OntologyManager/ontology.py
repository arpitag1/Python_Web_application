from rdflib import Graph, Namespace, RDF, RDFS, OWL, Literal
from pathlib import Path

DATA_DIR = Path("data")
ONTOLOGY_FILE = DATA_DIR / "ontology.ttl"

EX = Namespace("http://example.org/omics/")


class OntologyManager:

    def __init__(self):
        DATA_DIR.mkdir(exist_ok=True)

        self.graph = Graph()

        self.graph.bind("ex", EX)
        self.graph.bind("owl", OWL)
        self.graph.bind("rdfs", RDFS)

        if ONTOLOGY_FILE.exists():
            self.graph.parse(ONTOLOGY_FILE, format="turtle")
        else:
            self.create_initial_ontology()
            self.save()

    def create_initial_ontology(self):

        classes = {
            "Study": "A scientific research study",
            "Subject": "A participant or biological subject",
            "Sample": "A biological sample",
            "Assay": "An experimental measurement or analysis"
        }

        for name, description in classes.items():

            uri = EX[name]

            self.graph.add(
                (uri, RDF.type, OWL.Class)
            )

            self.graph.add(
                (uri, RDFS.label, Literal(name))
            )

            self.graph.add(
                (uri, RDFS.comment, Literal(description))
            )

        self.add_relationship(
            "hasSubject",
            "Study",
            "Subject"
        )

        self.add_relationship(
            "providesSample",
            "Subject",
            "Sample"
        )

        self.add_relationship(
            "analysedBy",
            "Sample",
            "Assay"
        )

    def add_class(self, name, description="", parent=None):

        uri = EX[name]

        self.graph.add(
            (uri, RDF.type, OWL.Class)
        )

        self.graph.add(
            (uri, RDFS.label, Literal(name))
        )

        if description:
            self.graph.add(
                (uri, RDFS.comment, Literal(description))
            )

        if parent:
            self.graph.add(
                (uri, RDFS.subClassOf, EX[parent])
            )

        self.save()

    def add_relationship(
        self,
        relationship,
        domain,
        range_class
    ):

        uri = EX[relationship]

        self.graph.add(
            (uri, RDF.type, OWL.ObjectProperty)
        )

        self.graph.add(
            (uri, RDFS.label, Literal(relationship))
        )

        self.graph.add(
            (uri, RDFS.domain, EX[domain])
        )

        self.graph.add(
            (uri, RDFS.range, EX[range_class])
        )

        self.save()

    def get_classes(self):

        classes = []

        for subject in self.graph.subjects(
            RDF.type,
            OWL.Class
        ):

            label = self.graph.value(
                subject,
                RDFS.label
            )

            description = self.graph.value(
                subject,
                RDFS.comment
            )

            parent = self.graph.value(
                subject,
                RDFS.subClassOf
            )

            classes.append({
                "name": str(label),
                "description": str(description or ""),
                "parent": (
                    self.get_local_name(parent)
                    if parent
                    else ""
                )
            })

        return classes

    def get_relationships(self):

        relationships = []

        for subject in self.graph.subjects(
            RDF.type,
            OWL.ObjectProperty
        ):

            label = self.graph.value(
                subject,
                RDFS.label
            )

            domain = self.graph.value(
                subject,
                RDFS.domain
            )

            range_class = self.graph.value(
                subject,
                RDFS.range
            )

            relationships.append({
                "relationship": str(label),
                "from": self.get_local_name(domain),
                "to": self.get_local_name(range_class)
            })

        return relationships

    def get_local_name(self, uri):

        if uri is None:
            return ""

        return str(uri).split("/")[-1]

    def save(self):

        self.graph.serialize(
            destination=ONTOLOGY_FILE,
            format="turtle"
        )
