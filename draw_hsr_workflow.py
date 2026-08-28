import os
graphviz_path = r"C:\Program Files\Graphviz\bin"
if os.path.exists(graphviz_path):
    os.environ["PATH"] = graphviz_path + os.pathsep + os.environ.get("PATH", "")

from diagrams import Diagram, Cluster, Edge
from diagrams.programming.flowchart import Action, Database
from diagrams.generic.storage import Storage

with Diagram(
    "HSR Dream Team Workflow with BIM",
    show=False,
    filename="G:/My Drive/AI-SUC TAI COC THEO DAT NEN/hsr_workflow",
    outformat="png",
    direction="TB",
    graph_attr={
        "pad": "1.5", "nodesep": "1.5", "ranksep": "2.5",
        "splines": "ortho", "dpi": "300"
    },
    node_attr={
        "fontsize": "20", "margin": "0.5,0.3",
        "width": "3.5", "height": "1.2"
    },
    edge_attr={
        "fontsize": "16", "minlen": "2"
    }
):
    bim = Database("Mô Hình BIM\n(Tệp chuẩn IFC)")
    
    with Cluster("Động Lực Học Đa Vật Thể (MBD)"):
        chrono = Action("Project Chrono\n(Bánh tàu & Toa xe)")
        
    with Cluster("Phần tử Hữu hạn (FEA)"):
        code_aster = Action("Code_Aster\n(Cầu & Mặt đường)")

    with Cluster("Động lực học Lưu chất (CFD)"):
        openfoam = Action("OpenFOAM\n(Gió & Khí động học)")
        
    precice = Storage("preCICE\n(Động cơ nội suy & Ghép nối đa vật lý)")

    # Data from BIM
    bim >> Edge(color="#0F172A", label="Trích xuất Hình học & Vật liệu\n(Chuyển sang Mesh/CAD)") >> code_aster
    bim >> Edge(color="#0F172A") >> openfoam
    
    # Simulation Coupling
    chrono >> Edge(color="#DC2626", label="Động lực bánh xe", dir="both") >> precice
    openfoam >> Edge(color="#0284C7", label="Áp suất gió tạt ngang", dir="both") >> precice
    code_aster >> Edge(color="#16A34A", label="Phản lực dầm cầu", dir="both") >> precice
    
    # Results back to BIM
    code_aster >> Edge(color="#E11D48", label="Ghi ngược kết quả\n(Cập nhật Property Sets phục vụ Vận hành & Bảo trì)", style="dashed") >> bim
