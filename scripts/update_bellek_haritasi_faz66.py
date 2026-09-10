import os

path = r"C:\Users\batu_\OneDrive\Belgeler\Obsidian Vault\Entropy\BELLEK_HARITASI.md"
with open(path, "r", encoding="utf-8") as f:
    content = f.read()

target = "| :--- | :--- | :---: | :--- |\n"
new_rows = (
    "| [[Gorev_Finans Yeteneği Geliştirme_20260906_1615|Gorev Finans Yeteneği Geliştirme 20260906 1615]] | `Gorev_Finans Yeteneği Geliştirme_20260906_1615.md` | **3** | 2026-09-06 16:15 |\n"
    "| [[HarrisonPliska_HJM_LucasTree_HuangStoll_GRS_ve_ChristoffersenKupiec|HarrisonPliska HJM LucasTree HuangStoll GRS ve ChristoffersenKupiec]] | `HarrisonPliska_HJM_LucasTree_HuangStoll_GRS_ve_ChristoffersenKupiec.md` | **3** | 2026-09-06 16:15 |\n"
)

if target in content:
    new_content = content.replace(target, target + new_rows, 1)
    with open(path, "w", encoding="utf-8") as f:
        f.write(new_content)
    print("SUCCESS: Updated BELLEK_HARITASI.md with Faz 66 entries")
else:
    print("ERROR: Target table header not found")
