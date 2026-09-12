from agent_analysis.quality_report import build_quality_report
def test_duplicate_frames_do_not_inflate_unique_count(tmp_path):
    p=tmp_path/'b.csv'; p.write_text('Frame,Visibility,X,Y,ball_speed_mps\n1,1,1,1,2\n1,1,1,1,2\n2,1,2,2,3\n',encoding='utf8')
    r=build_quality_report({'frame_count':2,'fps':30},p,None,True)
    assert r['unique_frame_count']==2 and r['valid_unique_frame_count']==2 and r['valid_frame_count']==2 and r['duplicate_frame_count']==1

def test_duplicate_valid_rows_do_not_inflate_coverage(tmp_path):
    p=tmp_path/'b.csv'; p.write_text('Frame,Visibility,X,Y\n1,1,1,1\n1,1,1,1\n',encoding='utf8')
    r=build_quality_report({'frame_count':1,'fps':30},p,None,True)
    assert r['valid_frame_count']==1 and r['valid_unique_frame_count']==1 and r['ball_visible_ratio']==1.0
def test_missing_and_invalid_values_are_visible(tmp_path):
    p=tmp_path/'b.csv'; p.write_text('Frame,Visibility,X,Y,ball_speed_mps\na,2,x,y,bad\n',encoding='utf8')
    r=build_quality_report({'frame_count':1,'fps':30},p,None,True)
    assert r['invalid_row_count']>0 and 'invalid_rows' in r['suspicious_metric_flags']
def test_schema_version(tmp_path):
    p=tmp_path/'b.csv'; p.write_text('Frame,Visibility,X,Y\n1,0,-1,-1\n',encoding='utf8')
    assert build_quality_report({'frame_count':1,'fps':30},p,None,True)['schema_version']=='1.0'

def test_unique_frame_fields(tmp_path):
    p=tmp_path/'b.csv'; p.write_text('Frame,Visibility,X,Y\n1,1,1,1\n2,0,-1,-1\n',encoding='utf8')
    r=build_quality_report({'frame_count':2,'fps':30},p,None,True)
    assert r['unique_frame_count']==2 and r['valid_unique_frame_count']==1
def test_non_monotonic_warning(tmp_path):
    p=tmp_path/'b.csv'; p.write_text('Frame,Visibility,X,Y\n2,1,1,1\n1,1,2,2\n',encoding='utf8')
    r=build_quality_report({'frame_count':2,'fps':30},p,None,True)
    assert r['non_monotonic_frame_count']==1
def test_missing_field_count(tmp_path):
    p=tmp_path/'b.csv'; p.write_text('Frame,Visibility\n1,1\n',encoding='utf8')
    assert build_quality_report({'frame_count':1,'fps':30},p,None,True)['missing_field_count']>=2
def test_per_rally_unavailable(tmp_path):
    p=tmp_path/'b.csv'; p.write_text('Frame,Visibility,X,Y\n1,0,-1,-1\n',encoding='utf8')
    r=build_quality_report({'frame_count':1,'fps':30},p,None,True)
    assert r['per_rally_quality_summary']['available'] is False
def test_duplicate_flag(tmp_path):
    p=tmp_path/'b.csv'; p.write_text('Frame,Visibility,X,Y\n1,1,1,1\n1,1,2,2\n',encoding='utf8')
    assert 'duplicate_frames' in build_quality_report({'frame_count':2,'fps':30},p,None,True)['suspicious_metric_flags']
def test_nonfinite_count(tmp_path):
    p=tmp_path/'b.csv'; p.write_text('Frame,Visibility,X,Y\nnan,1,1,1\n',encoding='utf8')
    assert build_quality_report({'frame_count':1,'fps':30},p,None,True)['non_finite_value_count'] >= 1
def test_speed_percentiles(tmp_path):
    p=tmp_path/'b.csv'; p.write_text('Frame,Visibility,X,Y,ball_speed_mps\n1,1,1,1,1\n2,1,2,2,2\n3,1,3,3,3\n',encoding='utf8')
    r=build_quality_report({'frame_count':3,'fps':30},p,None,True)
    assert r['ball_speed_max_mps']==3 and r['ball_speed_p99_mps'] is not None
def test_invalid_visibility_warning(tmp_path):
    p=tmp_path/'b.csv'; p.write_text('Frame,Visibility,X,Y\n1,no,1,1\n',encoding='utf8')
    assert 'invalid_rows' in build_quality_report({'frame_count':1,'fps':30},p,None,True)['suspicious_metric_flags']

def test_player_schema_missing_fields(tmp_path):
    ball=tmp_path/'b.csv'; ball.write_text('Frame,Visibility,X,Y\n1,1,1,1\n',encoding='utf8')
    player=tmp_path/'p.csv'; player.write_text('frame,player_near_x\n1,1\n',encoding='utf8')
    assert build_quality_report({'frame_count':1,'fps':30},ball,player,True)['missing_field_count'] >= 2

def test_invalid_visibility_is_counted(tmp_path):
    p=tmp_path/'b.csv'; p.write_text('Frame,Visibility,X,Y\n1,2,1,1\n',encoding='utf8')
    assert build_quality_report({'frame_count':1,'fps':30},p,None,True)['invalid_row_count'] == 1
