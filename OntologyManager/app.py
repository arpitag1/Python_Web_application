import streamlit as st
from ontology import OntologyManager
from pyvis.network import Network
import streamlit.components.v1 as components


st.set_page_config(
    page_title="Simple Ontology Manager",
    layout="wide"
)

manager = OntologyManager()


st.title("Simple Ontology Manager")

st.caption(
    "Create and explore a small scientific ontology"
)


# ---------------------------------------------------
# Sidebar
# ---------------------------------------------------

st.sidebar.header("Navigation")

page = st.sidebar.radio(
    "Go to",
    [
        "Ontology Overview",
        "Manage Classes",
        "Manage Relationships",
        "Graph View",
        "Export Ontology"
    ]
)


# ---------------------------------------------------
# OVERVIEW
# ---------------------------------------------------

if page == "Ontology Overview":

    st.header("Ontology Overview")

    classes = manager.get_classes()
    relationships = manager.get_relationships()

    col1, col2 = st.columns(2)

    with col1:

        st.metric(
            "Classes",
            len(classes)
        )

    with col2:

        st.metric(
            "Relationships",
            len(relationships)
        )

    st.subheader("Classes")

    st.dataframe(
        classes,
        use_container_width=True
    )

    st.subheader("Relationships")

    st.dataframe(
        relationships,
        use_container_width=True
    )


# ---------------------------------------------------
# MANAGE CLASSES
# ---------------------------------------------------

elif page == "Manage Classes":

    st.header("Manage Ontology Classes")

    st.subheader("Existing Classes")

    classes = manager.get_classes()

    st.dataframe(
        classes,
        use_container_width=True
    )

    st.divider()

    st.subheader("Add New Class")

    class_names = [
        item["name"]
        for item in classes
    ]

    name = st.text_input(
        "Class name"
    )

    description = st.text_area(
        "Description"
    )

    parent_options = [
        "None"
    ] + class_names

    parent = st.selectbox(
        "Parent class",
        parent_options
    )

    if st.button("Add Class"):

        if name.strip():

            manager.add_class(
                name.strip(),
                description.strip(),
                None if parent == "None" else parent
            )

            st.success(
                f"Class '{name}' added successfully."
            )

            st.rerun()

        else:

            st.error(
                "Please enter a class name."
            )


# ---------------------------------------------------
# RELATIONSHIP MANAGEMENT
# ---------------------------------------------------

elif page == "Manage Relationships":

    st.header("Manage Relationships")

    relationships = manager.get_relationships()

    st.subheader("Existing Relationships")

    st.dataframe(
        relationships,
        use_container_width=True
    )

    st.divider()

    st.subheader("Create Relationship")

    classes = manager.get_classes()

    class_names = [
        item["name"]
        for item in classes
    ]

    relationship_name = st.text_input(
        "Relationship name",
        placeholder="e.g. hasSample"
    )

    source = st.selectbox(
        "From class",
        class_names
    )

    target = st.selectbox(
        "To class",
        class_names
    )

    if st.button("Add Relationship"):

        if relationship_name.strip():

            manager.add_relationship(
                relationship_name.strip(),
                source,
                target
            )

            st.success(
                "Relationship created."
            )

            st.rerun()

        else:

            st.error(
                "Please enter the relationship name."
            )


# ---------------------------------------------------
# GRAPH VISUALIZATION
# ---------------------------------------------------

elif page == "Graph View":

    st.header("Ontology Graph")

    relationships = manager.get_relationships()
    classes = manager.get_classes()

    network = Network(
        height="600px",
        width="100%",
        directed=True
    )

    network.toggle_physics(True)

    for ontology_class in classes:

        network.add_node(
            ontology_class["name"],
            label=ontology_class["name"],
            color="#4C78A8",
            shape="box"
        )

    for rel in relationships:

        network.add_edge(
            rel["from"],
            rel["to"],
            label=rel["relationship"],
            arrows="to"
        )

    network.save_graph("ontology_graph.html")

    with open(
        "ontology_graph.html",
        "r",
        encoding="utf-8"
    ) as file:

        html = file.read()

    components.html(
        html,
        height=650,
        scrolling=True
    )


# ---------------------------------------------------
# EXPORT
# ---------------------------------------------------

elif page == "Export Ontology":

    st.header("Export Ontology")

    turtle_data = manager.graph.serialize(
        format="turtle"
    )

    st.subheader("OWL/RDF Turtle")

    st.code(
        turtle_data,
        language="turtle"
    )

    st.download_button(
        label="Download ontology.ttl",
        data=turtle_data,
        file_name="ontology.ttl",
        mime="text/turtle"
    )