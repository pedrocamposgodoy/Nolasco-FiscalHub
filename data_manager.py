import pandas as pd
import numpy as np

def clean_fiscal_data(df):
    """
    Limpia las 55 columnas de Supabase y asegura que 
    los cálculos no den error (evita NaNs).
    """
    if df.empty:
        return df
    
    # 1. Convertir columnas numéricas críticas
    cols_numericas = [
        'renta', 'ibi_anual', 'seguro_anual', 'intereses_hipoteca', 
        'comunidad', 'amortizacion_fiscal', 'precio_compra', 'valor_catastral'
    ]
    
    for col in cols_numericas:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0.0)
    
    # 2. Crear columnas calculadas para la demo
    # Rendimiento Bruto Anual
    df['ingresos_anuales'] = df['renta'] * 12
    
    # Gastos deducibles totales (Capa 1)
    df['gastos_totales'] = (
        df['ibi_anual'] + df['seguro_anual'] + 
        df['comunidad'] + df['intereses_hipoteca'] + 
        df['amortizacion_fiscal']
    )
    
    # Rendimiento Neto
    df['rendimiento_neto'] = df['ingresos_anuales'] - df['gastos_totales']
    
    return df

def get_resumen_por_propietario(df):
    """
    Agrupa los inmuebles para mostrar al asesor 
    cuánto gana en total cada uno de sus 3 clientes.
    """
    resumen = df.groupby('titular').agg({
        'id': 'count',
        'ingresos_anuales': 'sum',
        'rendimiento_neto': 'sum',
        'amortizacion_fiscal': 'sum'
    }).reset_index()
    
    resumen.columns = ['Propietario', 'Nº Inmuebles', 'Total Ingresos', 'Rendimiento Neto Total', 'Amortización Acum.']
    return resumen
