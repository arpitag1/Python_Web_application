import streamlit as st
import streamlit.components.v1 as components
import pandas as pd
from neo4j import GraphDatabase
from pyvis.network import Network

st.set_page_config(page_title="Data Office Product Explorer", layout="wide")
st.title("Data Office Data Product Explorer")

NODE_TYPES = {"System", "DataAsset", "DataProduct", "API", "Report", "Owner", "Steward", "DataDomain"}
REL_TYPES = {"PROVIDES", "USES", "EXPOSES", "CONSUMES", "OWNS", "STEWARDS", "HAS_PRODUCT", "DEPENDS_ON"}
COLORS = {
    "System":"#dc2626", "DataAsset": "#059669", "DataProduct": "#4f46e5",
    "API": "#d97706", "Report": "#7c3aed", "Owner": "#0891b2",
    "Steward": "#0f766e", "DataDomain": "#475569"
}
REQUIRED_COLUMNS = {
    "source_type", "source_name", "relationship", "target_type", "target_name",
    "source_subtype", "target_subtype", "source_domain", "target_domain",
    "source_criticality", "target_criticality", "source_classification",
    "target_classification", "source_quality_status", "target_quality_status",
    "source_lifecycle_status", "target_lifecycle_status", "source_fair_status",
    "target_fair_status", "source_description", "target_description"
}

# ---------- Connection ----------
st.sidebar.header("Neo4j connection")
uri = st.sidebar.text_input("URI", "neo4j://localhost:7687")
username = st.sidebar.text_input("Username", "neo4j")
password = st.sidebar.text_input("Password", type="password")

@st.cache_resource
def connect(uri_value, user_value, password_value):
    neo4j_driver = GraphDatabase.driver(uri_value, auth=(user_value, password_value))
    neo4j_driver.verify_connectivity()
    return neo4j_driver


def online_databases(neo4j_driver):
    with neo4j_driver.session(database="system") as session:
        return [r["name"] for r in session.run("""
            SHOW DATABASES YIELD name, currentStatus
            WHERE currentStatus = 'online'
            RETURN name ORDER BY name
        """)]

if not password:
    st.info("Enter the Neo4j password in the sidebar.")
    st.stop()

try:
    driver = connect(uri, username, password)
    databases = online_databases(driver)
    database = st.sidebar.selectbox("Database", databases)
except Exception as exc:
    st.error(f"Neo4j connection failed: {exc}")
    st.stop()

page = st.sidebar.radio("Menu", [
    "Overview", "Upload Data", "Data Product Catalogue", "Product Details",
    "Dependency & Lineage", "Impact Analysis", "Governance Dashboard"
])


def product_names():
    with driver.session(database=database) as session:
        return [r["name"] for r in session.run(
            "MATCH (p:DataProduct) RETURN p.name AS name ORDER BY name"
        )]


def graph_html(rows, highlighted=None):
    net = Network(height="610px", width="100%", directed=True, bgcolor="#ffffff")
    net.set_options('''{
      "interaction":{"hover":true,"navigationButtons":true},
      "physics":{"stabilization":true},
      "edges":{"arrows":{"to":{"enabled":true}}}
    }''')
    for row in rows:
        for side in ("source", "target"):
            name, node_type = row[side], row[f"{side}_type"]
            net.add_node(name, label=name, color=COLORS.get(node_type, "#64748b"),
                         title=node_type, size=30 if name == highlighted else 20)
        net.add_edge(row["source"], row["target"], label=row["relationship"])
    return net.generate_html(notebook=False)

# ---------- Overview ----------
if page == "Overview":
    with driver.session(database=database) as session:
        counts = [dict(r) for r in session.run("""
            MATCH (n) UNWIND labels(n) AS node_type
            RETURN node_type, count(*) AS total ORDER BY node_type
        """)]
    if counts:
        cols = st.columns(min(4, len(counts)))
        for i, item in enumerate(counts):
            cols[i % len(cols)].metric(item["node_type"], item["total"])
        st.dataframe(pd.DataFrame(counts), use_container_width=True, hide_index=True)
    else:
        st.info("No data loaded.")

# ---------- Upload ----------
elif page == "Upload Data":
    st.subheader("Upload governance data")
    uploaded = st.file_uploader("Upload data_office_sample.csv", type="csv")
    if uploaded:
        df = pd.read_csv(uploaded).fillna("")
        df.columns = [c.strip() for c in df.columns]
        st.dataframe(df, use_container_width=True, hide_index=True)
        missing = sorted(REQUIRED_COLUMNS - set(df.columns))
        if missing:
            st.error("Missing columns: " + ", ".join(missing))
        elif st.button("Load into Neo4j", type="primary"):
            try:
                with driver.session(database=database) as session:
                    for _, row in df.iterrows():
                        s_type = str(row.source_type).strip()
                        t_type = str(row.target_type).strip()
                        rel = str(row.relationship).strip().upper()
                        if s_type not in NODE_TYPES or t_type not in NODE_TYPES or rel not in REL_TYPES:
                            raise ValueError(f"Invalid model value: {s_type}-{rel}-{t_type}")
                        query = f"""
                        MERGE (s:{s_type} {{name:$source_name}})
                        SET s.subtype=$source_subtype, s.domain=$source_domain,
                            s.criticality=$source_criticality, s.classification=$source_classification,
                            s.quality_status=$source_quality_status,
                            s.lifecycle_status=$source_lifecycle_status,
                            s.fair_status=$source_fair_status, s.description=$source_description
                        MERGE (t:{t_type} {{name:$target_name}})
                        SET t.subtype=$target_subtype, t.domain=$target_domain,
                            t.criticality=$target_criticality, t.classification=$target_classification,
                            t.quality_status=$target_quality_status,
                            t.lifecycle_status=$target_lifecycle_status,
                            t.fair_status=$target_fair_status, t.description=$target_description
                        MERGE (s)-[:{rel}]->(t)
                        """
                        session.run(query, **{c: str(row[c]).strip() for c in REQUIRED_COLUMNS if c != "relationship"}).consume()
                st.success(f"Loaded {len(df)} records into '{database}'.")
            except Exception as exc:
                st.error(f"Load failed: {exc}")

# ---------- Catalogue ----------
elif page == "Data Product Catalogue":
    st.subheader("Data Product Catalogue")
    with driver.session(database=database) as session:
        rows = [dict(r) for r in session.run("""
            MATCH (p:DataProduct)
            OPTIONAL MATCH (o:Owner)-[:OWNS]->(p)
            OPTIONAL MATCH (s:Steward)-[:STEWARDS]->(p)
            OPTIONAL MATCH (d:DataDomain)-[:HAS_PRODUCT]->(p)
            RETURN p.name AS data_product, coalesce(d.name,p.domain) AS domain,
                   o.name AS owner, s.name AS steward, p.criticality AS criticality,
                   p.classification AS classification, p.quality_status AS quality_status,
                   p.lifecycle_status AS lifecycle_status, p.fair_status AS fair_status
            ORDER BY data_product
        """)]
    if rows:
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
    else:
        st.info("No Data Products found.")

# ---------- Details ----------
elif page == "Product Details":
    st.subheader("Data Product Details")
    products = product_names()
    if not products:
        st.info("Load data first.")
    else:
        selected = st.selectbox("Data Product", products)
        with driver.session(database=database) as session:
            product = session.run("""
                MATCH (p:DataProduct {name:$name})
                RETURN properties(p) AS details
            """, name=selected).single()["details"]
            connections = [dict(r) for r in session.run("""
                MATCH (p:DataProduct {name:$name})-[r]-(n)
                RETURN type(r) AS relationship, labels(n)[0] AS node_type,
                       n.name AS connected_name, n.subtype AS subtype
                ORDER BY relationship, connected_name
            """, name=selected)]
        st.json(product)
        st.dataframe(pd.DataFrame(connections), use_container_width=True, hide_index=True)

# ---------- Dependency ----------
elif page == "Dependency & Lineage":
    st.subheader("Dependency and Lineage")
    products = product_names()
    if not products:
        st.info("Load data first.")
    else:
        selected = st.selectbox("Data Product", products)
        with driver.session(database=database) as session:
            rows = [dict(r) for r in session.run("""
                MATCH path=(p:DataProduct {name:$name})-[*1..3]-(n)
                UNWIND relationships(path) AS rel
                RETURN DISTINCT startNode(rel).name AS source,
                       labels(startNode(rel))[0] AS source_type,
                       type(rel) AS relationship, endNode(rel).name AS target,
                       labels(endNode(rel))[0] AS target_type
                LIMIT 250
            """, name=selected)]
        if rows:
            components.html(graph_html(rows, selected), height=640, scrolling=True)
        else:
            st.info("No dependencies found.")

# ---------- Impact ----------
elif page == "Impact Analysis":
    st.subheader("Impact Analysis")
    with driver.session(database=database) as session:
        starts = [dict(r) for r in session.run("""
            MATCH (n) WHERE n:System OR n:DataAsset
            RETURN labels(n)[0] AS node_type, n.name AS name, n.subtype AS subtype
            ORDER BY node_type, name
        """)]
    if not starts:
        st.info("No System or Data Asset nodes found.")
    else:
        labels = [f"{x['node_type']}: {x['name']}" for x in starts]
        selected_label = st.selectbox("Select System or Data Asset", labels)
        selected = starts[labels.index(selected_label)]
        if st.button("Analyse Impact", type="primary"):
            start_label = selected["node_type"]
            with driver.session(database=database) as session:
                table_rows = [dict(r) for r in session.run(f"""
                    MATCH path=(start:{start_label} {{name:$name}})-[*1..6]-(n)
                    WHERE n:DataProduct OR n:API OR n:Report
                    OPTIONAL MATCH (o:Owner)-[:OWNS]->(n)
                    OPTIONAL MATCH (s:Steward)-[:STEWARDS]->(n)
                    RETURN DISTINCT labels(n)[0] AS type, n.name AS name,
                           length(path) AS distance, o.name AS owner, s.name AS steward,
                           n.criticality AS criticality, n.quality_status AS quality_status
                    ORDER BY distance, type, name LIMIT 150
                """, name=selected["name"])]
                graph_rows = [dict(r) for r in session.run(f"""
                    MATCH path=(start:{start_label} {{name:$name}})-[*1..6]-(n)
                    WHERE n:DataProduct OR n:API OR n:Report
                    UNWIND relationships(path) AS rel
                    RETURN DISTINCT startNode(rel).name AS source,
                           labels(startNode(rel))[0] AS source_type,
                           type(rel) AS relationship, endNode(rel).name AS target,
                           labels(endNode(rel))[0] AS target_type LIMIT 300
                """, name=selected["name"])]
            if table_rows:
                st.markdown("### Table view")
                st.dataframe(pd.DataFrame(table_rows), use_container_width=True, hide_index=True)
                st.markdown("### Pictorial view")
                components.html(graph_html(graph_rows, selected["name"]), height=640, scrolling=True)
            else:
                st.info("No impact found.")

# ---------- Governance ----------
elif page == "Governance Dashboard":
    st.subheader("Governance Dashboard")
    with driver.session(database=database) as session:
        summary = session.run("""
            MATCH (p:DataProduct)
            OPTIONAL MATCH (:Owner)-[:OWNS]->(p)
            WITH p, count(*) AS owner_matches
            OPTIONAL MATCH (:Steward)-[:STEWARDS]->(p)
            RETURN count(DISTINCT p) AS total_products,
                   count(DISTINCT CASE WHEN owner_matches = 0 THEN p END) AS missing_owner,
                   count(DISTINCT CASE WHEN p.criticality = 'High' THEN p END) AS critical_products,
                   count(DISTINCT CASE WHEN p.quality_status <> 'Passed' THEN p END) AS quality_attention,
                   count(DISTINCT CASE WHEN p.fair_status <> 'Assessed' THEN p END) AS fair_attention
        """).single()
        gaps = [dict(r) for r in session.run("""
            MATCH (p:DataProduct)
            OPTIONAL MATCH (o:Owner)-[:OWNS]->(p)
            OPTIONAL MATCH (s:Steward)-[:STEWARDS]->(p)
            WITH p, o, s,
                 [x IN [CASE WHEN o IS NULL THEN 'Owner' END,
                        CASE WHEN s IS NULL THEN 'Steward' END,
                        CASE WHEN coalesce(p.classification,'')='' THEN 'Classification' END,
                        CASE WHEN coalesce(p.quality_status,'')='' THEN 'Quality status' END]
                  WHERE x IS NOT NULL] AS gaps
            WHERE size(gaps) > 0
            RETURN p.name AS data_product, gaps AS missing_metadata
            ORDER BY data_product
        """)]
    values = dict(summary)
    cols = st.columns(5)
    for col, (label, value) in zip(cols, values.items()):
        col.metric(label.replace("_", " ").title(), value)
    st.markdown("### Governance gaps")
    if gaps:
        st.dataframe(pd.DataFrame(gaps), use_container_width=True, hide_index=True)
    else:
        st.success("No configured governance gaps found.")
