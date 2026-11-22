"""Check regenerated JME output coverage and existing accounting identities."""
from pathlib import Path
import json
import numpy as np
import pandas as pd
ROOT=Path(__file__).resolve().parents[1]
def main():
    mapping=pd.read_csv(ROOT/'documentation/exhibit_map.csv').query("status=='included_empirical'")
    for rel in mapping.output:assert (ROOT/rel).is_file(),f'Missing generated exhibit: {rel}'
    cells=pd.read_csv(ROOT/'output/numerical/display_cells.csv')
    contract=json.loads((ROOT/'config/replication_contract.json').read_text())
    assert cells.table.nunique()==22 and len(cells)==contract['display_cells']
    assert set(cells.table)==set(mapping.latex_label[mapping.exhibit.str.startswith('Table')])
    c=pd.read_csv(ROOT/'results/return_components.csv')
    np.testing.assert_allclose(c.realized_return,c.expected_return+c.cash_flow_news-c.discount_rate_news,atol=1e-12,rtol=1e-12)
    v=pd.read_csv(ROOT/'results/channel_var.csv')
    np.testing.assert_allclose(v.beta_total,v.beta_ER+v.beta_CF-v.beta_DR,atol=1e-12,rtol=1e-12)
    f=pd.read_csv(ROOT/'results/return_forecasts.csv',low_memory=False)
    assert (f.max_training_target_end<=f.forecast_origin).all()
    fig=pd.read_csv(ROOT/'output/numerical/figure_2_source_check.csv')
    assert len(fig)==4 and fig.status.eq('PASS').all()
    print(json.dumps(dict(status='PASS',empirical_tables=22,empirical_figures=3,display_cells=len(cells),checks=['exhibit coverage','return component identities','mature training windows','Figure 2/Table 1 consistency'])))
if __name__=='__main__':main()
