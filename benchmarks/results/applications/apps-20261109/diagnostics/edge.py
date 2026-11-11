"""Cell extent and voxel crowding per snapshot. Usage: edge.py OUTPUT_DIR HALF_WIDTH DX SNAPSHOT..."""
import sys, numpy as np, scipy.io as sio, xml.etree.ElementTree as ET
from collections import Counter
out, half, dx = sys.argv[1], float(sys.argv[2]), float(sys.argv[3])
for n in sys.argv[4:]:
    r = ET.parse(f'{out}/output{int(n):08d}.xml').getroot()
    labels = {l.text: int(l.get('index')) for l in r.iter('label')}
    c = sio.loadmat(f'{out}/output{int(n):08d}_cells.mat')['cells']
    px, py = c[labels['position']], c[labels['position']+1]
    vox = Counter(zip(np.floor((px+half)/dx).astype(int), np.floor((py+half)/dx).astype(int)))
    occ = np.array(list(vox.values()))
    print(f"t={float(r.findtext('.//current_time')):.0f} cells={c.shape[1]} x[{px.min():.2f},{px.max():.2f}] y[{py.min():.2f},{py.max():.2f}] "
          f"outside={int(((abs(px)>half)|(abs(py)>half)).sum())} within2um={int(((abs(px)>half-2)|(abs(py)>half-2)).sum())} "
          f"cells_per_occupied_voxel mean={occ.mean():.2f} max={occ.max()}")
