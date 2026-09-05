from ver2_official_live_fetcher import parse_roster

HTML='''<table><tbody>
<tr><td>１</td><td>3580 / B1 <a href="/owpc/pc/data/racersearch/profile?toban=3580">水口　　由紀</a> 53歳/48.6kg</td><td>3 41.86 55.81 17 36.23 54.11</td></tr>
<tr><td>２</td><td>3801 / B1 <a href="/owpc/pc/data/racersearch/profile?toban=3801">五反田　　忍</a> 52歳/51.3kg</td><td>9 28.89 37.78 18 36.54 53.85</td></tr>
<tr><td>３</td><td>3611 / A2 <a href="/owpc/pc/data/racersearch/profile?toban=3611">岩崎　　芳美</a> 54歳/47.7kg</td><td>55 48.94 65.96 62 36.87 53.00</td></tr>
<tr><td>４</td><td>4317 / B1 <a href="/owpc/pc/data/racersearch/profile?toban=4317">木村　紗友希</a> 42歳/46.5kg</td><td>14 33.33 57.47 48 36.23 51.21</td></tr>
<tr><td>５</td><td>3579 / B1 <a href="/owpc/pc/data/racersearch/profile?toban=3579">中里　　優子</a> 53歳/47.8kg</td><td>58 28.24 50.59 23 33.02 49.30</td></tr>
<tr><td>６</td><td>4225 / A2 <a href="/owpc/pc/data/racersearch/profile?toban=4225">土屋　　千明</a> 44歳/46.0kg</td><td>20 46.08 65.69 14 36.87 54.55</td></tr>
</tbody></table>'''

boats=parse_roster(HTML)
assert [b['boat_no'] for b in boats] == [1,2,3,4,5,6]
assert [b['racer_name'] for b in boats] == ['水口由紀','五反田忍','岩崎芳美','木村紗友希','中里優子','土屋千明']
assert [b['motor_no'] for b in boats] == [3,9,55,14,58,20]
assert boats[0]['motor_3rentai_rate'] == 55.81
assert boats[5]['motor_3rentai_rate'] == 65.69
print('fetcher fixture PASS')
