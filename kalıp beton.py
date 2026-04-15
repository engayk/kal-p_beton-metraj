import streamlit as st
import ezdxf
from ezdxf.path import from_hatch
import math
import tempfile
import os

# --- MATEMATİKSEL FONKSİYONLAR ---
def koordinatlardan_alan_hesapla(noktalar):
    """Gauss Alan Formülü (Shoelace) ile 2D poligon alanı hesaplar"""
    if len(noktalar) < 3: 
        return 0.0
    alan = 0.0
    n = len(noktalar)
    for i in range(n):
        j = (i + 1) % n
        # Hem ezdxf Vec3 objesini hem de standart tuple (x,y) listesini destekler
        x1 = noktalar[i].x if hasattr(noktalar[i], 'x') else noktalar[i][0]
        y1 = noktalar[i].y if hasattr(noktalar[i], 'y') else noktalar[i][1]
        x2 = noktalar[j].x if hasattr(noktalar[j], 'x') else noktalar[j][0]
        y2 = noktalar[j].y if hasattr(noktalar[j], 'y') else noktalar[j][1]
        alan += (x1 * y2) - (x2 * y1)
    return abs(alan) / 2.0

# --- ARAYÜZ AYARLARI ---
st.set_page_config(page_title="Metraj Motoru v2.0", page_icon="🏗️", layout="wide")

st.title("🏗️ Akıllı Kalıp ve Beton Metraj Motoru")
st.markdown("DXF içindeki katmanları okur; Kalıp için çevre, Beton için alan hesabı yapar.")

# --- DOSYA YÜKLEME ---
yuklenen_dosya = st.file_uploader("DXF Dosyasını Yükleyin", type=['dxf'])

if yuklenen_dosya:
    with tempfile.NamedTemporaryFile(delete=False, suffix=".dxf") as tmp:
        tmp.write(yuklenen_dosya.getvalue())
        tmp_path = tmp.name

    try:
        doc = ezdxf.readfile(tmp_path)
        msp = doc.modelspace()
        
        mevcut_katmanlar = [layer.dxf.name for layer in doc.layers]
        mevcut_katmanlar.sort()

        # --- YAN MENÜ AYARLARI ---
        with st.sidebar:
            st.header("⚙️ Katman Seçimleri")
            secilen_kalip_katmanlari = st.multiselect("🔨 Kalıp Katmanları (Çevre x Yükseklik)", options=mevcut_katmanlar)
            secilen_beton_katmanlari = st.multiselect("🧊 Beton Katmanları (Alan x Yükseklik)", options=mevcut_katmanlar)
            
            st.divider()
            st.header("📐 Proje Parametreleri")
            cizim_birimi = st.selectbox("Çizim Birimi", ["Metre (m)", "Santimetre (cm)", "Milimetre (mm)"], index=1)
            
            # Uzunluk (Çevre) katsayısı
            uzunluk_katsayisi = {"Metre (m)": 1.0, "Santimetre (cm)": 0.01, "Milimetre (mm)": 0.001}[cizim_birimi]
            # Alan katsayısı (Katsayının karesi)
            alan_katsayisi = uzunluk_katsayisi ** 2 
            
            kat_yuksekligi = st.number_input("Kat Yüksekliği (m)", min_value=0.0, value=3.0, step=0.1)

        if not secilen_kalip_katmanlari and not secilen_beton_katmanlari:
            st.warning("👈 Lütfen sol taraftaki menüden Kalıp veya Beton için en az bir katman seçin.")
        else:
            # --- HESAPLAMA MOTORU ---
            toplam_cevre_cizim_birimi = 0.0
            toplam_taban_alani_cizim_birimi = 0.0
            okunan_kalip_nesne = 0
            okunan_beton_nesne = 0

            kalip_katman_upper = [s.upper() for s in secilen_kalip_katmanlari]
            beton_katman_upper = [s.upper() for s in secilen_beton_katmanlari]

            for entity in msp:
                layer_adi = entity.dxf.layer.upper()
                
                is_kalip = layer_adi in kalip_katman_upper
                is_beton = layer_adi in beton_katman_upper

                if not (is_kalip or is_beton):
                    continue

                # HATCH (TARAMA)
                if entity.dxftype() == 'HATCH':
                    try:
                        paths = from_hatch(entity)
                        for path in paths:
                            points = list(path.flattening(distance=0.01))
                            
                            # Kalıp için çevre topla
                            if is_kalip:
                                for i in range(len(points) - 1):
                                    toplam_cevre_cizim_birimi += math.dist((points[i].x, points[i].y), (points[i+1].x, points[i+1].y))
                                okunan_kalip_nesne += 1
                                
                            # Beton için poligon alanını topla
                            if is_beton:
                                toplam_taban_alani_cizim_birimi += koordinatlardan_alan_hesapla(points)
                                okunan_beton_nesne += 1
                    except:
                        continue
                
                # POLYLINE (SADECE KAPALI OLANLAR BETONA DAHİL EDİLİR)
                elif entity.dxftype() == 'LWPOLYLINE':
                    points = entity.get_points('xy')
                    
                    if is_kalip:
                        p_len = 0.0
                        for i in range(len(points) - 1):
                            p_len += math.dist(points[i], points[i+1])
                        if entity.closed:
                            p_len += math.dist(points[-1], points[0])
                        toplam_cevre_cizim_birimi += p_len
                        okunan_kalip_nesne += 1
                        
                    # Beton hesabı için polyline'ın mutlaka kapalı olması gerekir
                    if is_beton and entity.closed:
                        toplam_taban_alani_cizim_birimi += koordinatlardan_alan_hesapla(points)
                        okunan_beton_nesne += 1

            # --- BİRİM DÖNÜŞÜMLERİ VE NİHAİ HESAPLAR ---
            net_cevre_m = toplam_cevre_cizim_birimi * uzunluk_katsayisi
            net_taban_alani_m2 = toplam_taban_alani_cizim_birimi * alan_katsayisi
            
            toplam_kalip_m2 = net_cevre_m * kat_yuksekligi
            toplam_beton_m3 = net_taban_alani_m2 * kat_yuksekligi

            # --- SONUÇ EKRANI ---
            st.success("Tüm Metraj Hesaplamaları Başarıyla Tamamlandı!")
            
            col1, col2 = st.columns(2)
            
            with col1:
                st.subheader("🔨 KALIP METRAJI")
                st.metric("Toplam Kalıp Alanı", f"{toplam_kalip_m2:.2f} m²")
                st.write(f"**Okunan Nesne:** {okunan_kalip_nesne} Adet")
                st.write(f"**Toplam Çevre Uzunluğu:** {net_cevre_m:.2f} m")
                
            with col2:
                st.subheader("🧊 BETON METRAJI")
                st.metric("Toplam Beton Hacmi", f"{toplam_beton_m3:.2f} m³")
                st.write(f"**Okunan Nesne:** {okunan_beton_nesne} Adet")
                st.write(f"**Net Zemin Kesit Alanı:** {net_taban_alani_m2:.2f} m²")

    except Exception as e:
        st.error(f"Dosya okuma veya hesaplama hatası: {e}")
    finally:
        if 'tmp_path' in locals():
            os.remove(tmp_path)