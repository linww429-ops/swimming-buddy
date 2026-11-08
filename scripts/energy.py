"""Display energy in both units without changing source values."""
from decimal import Decimal,ROUND_HALF_UP

FACTOR=Decimal('4.184')
def rounded(value):return int(Decimal(value).quantize(Decimal('1'),rounding=ROUND_HALF_UP))
def normalized(metric):
    if metric.get('status')!='confirmed' or metric.get('key') not in ('calories','energy_kj'):return None
    unit=metric.get('unit');value=metric.get('value')
    if isinstance(value,bool) or not isinstance(value,(int,float)):return None
    if unit=='kcal':return Decimal(str(value))
    if unit=='kJ':return Decimal(str(value))/FACTOR
    return None
def display(metric):
    kcal=normalized(metric)
    if kcal is None:return None
    kj=Decimal(str(metric['value'])) if metric['unit']=='kJ' else kcal*FACTOR
    return f'{rounded(kcal)} 千卡 / {rounded(kj)} kJ'
