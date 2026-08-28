import os
graphviz_path = r"C:\Program Files\Graphviz\bin"
if os.path.exists(graphviz_path):
    os.environ["PATH"] = graphviz_path + os.pathsep + os.environ.get("PATH", "")

from diagrams import Diagram, Cluster, Edge
from diagrams.programming.flowchart import Action, Database
from diagrams.generic.storage import Storage

with Diagram(
    "FSI - SSI - BIM Workflow",
    show=False,
    filename="G:/My Drive/AI-SUC TAI COC THEO DAT NEN/fsi_ssi_bim_workflow",
    outformat="png",
    direction="LR",
    graph_attr={
        "pad": "1.5", "nodesep": "1.2", "ranksep": "2.0",
        "splines": "ortho", "dpi": "300"
    },
    node_attr={
        "fontsize": "32", "margin": "0.45,0.3",
        "width": "3.2", "height": "1.0"
    },
    edge_attr={
        "fontsize": "28", "minlen": "2"
    }
):
    bim = Database("BIM Model\n(IFC)")
    
    with Cluster("AI Orchestration"):
        ai_agent = Action("AI Agent\n(Scripting & Setup)")

    with Cluster("Multi-physics Simulation (HPC)"):
        openfoam = Action("OpenFOAM\n(CFD / Sóng & Gió)")
        code_aster = Action("Code_Aster\n(FEA / Kết cấu & Đất nền)")
        precice = Storage("preCICE\n(Coupling & Mapping)")
        
        openfoam >> Edge(color="#0284C7", label="Áp suất/Lực", dir="both", minlen="1") >> precice
        code_aster >> Edge(color="#16A34A", label="Biến dạng/Vị trí", dir="both", minlen="1") >> precice

    bim >> Edge(color="#0F172A", label="Trích xuất Hình học & Vật liệu") >> ai_agent
    ai_agent >> Edge(color="#0F172A", label="Tạo file cấu hình lưới") >> openfoam
    ai_agent >> Edge(color="#0F172A", label="Tạo file điều kiện biên") >> code_aster
    
    ai_agent >> Edge(color="#4F46E5", label="Điều phối chạy mô phỏng", style="dashed") >> precice
    
    results = Database("Kết quả Mô phỏng\n(Ứng suất, Độ lún)")
    code_aster >> Edge(color="#64748B", label="Xuất dữ liệu") >> results
    openfoam >> Edge(color="#64748B", label="Xuất dữ liệu") >> results
    
    results >> Edge(color="#D97706", label="Xử lý dữ liệu") >> ai_agent
    ai_agent >> Edge(color="#E11D48", label="Ghi ngược Psets vào IFC") >> bim
