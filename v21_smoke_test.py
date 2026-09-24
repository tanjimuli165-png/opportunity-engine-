from pathlib import Path
from tempfile import TemporaryDirectory
import subprocess

from app.collectors.marketplaces import MarketplaceCollector
from app.database.models import Evidence, MarketplaceGap, Report
from app.pdf.generator import benchmark_price, concise_text, generate_pdf
from app.product.launch_suite import natural_customer_language

long_text = "I keep losing valuable hours every single week because this complicated workflow is confusing and difficult to manage when I need a reliable result for my customers"
assert len(natural_customer_language(long_text).split()) <= 15
assert natural_customer_language(long_text).endswith("...")
assert concise_text(long_text).split()[-1] == "..."
assert benchmark_price("Not found", "Notion, Printable") == "$19 – $29 (Benchmark)"
assert benchmark_price("Not found", "Spreadsheet") == "$29 – $49 (Benchmark)"
assert benchmark_price("$12", "Printable") == "$12"
report = Report(id="v21", topic="Meal Prep", evidence=[Evidence(source="Etsy", title="Example", text="This is enough evidence text for a report.")], marketplace_gaps=[MarketplaceGap(marketplace="Etsy", title="Notion planner", price="Not found", format="Notion")], sales_hooks=[long_text], executive_summary="Test")
with TemporaryDirectory() as directory:
    path = Path(directory) / "report.pdf"
    generate_pdf(report, path)
    text = subprocess.run(["pdftotext", str(path), "-"], capture_output=True, text=True, check=True).stdout
    assert "19" in text and "Benchma" in text
print("V2.1 PDF formatting smoke test passed")
