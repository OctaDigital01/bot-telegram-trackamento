#!/usr/bin/env python3
"""
Script para verificar variáveis de mídia no Railway
"""
import os

def check_media_variables():
    """Verifica se todas as variáveis de mídia estão configuradas"""
    
    print("🔍 VERIFICANDO VARIÁVEIS DE MÍDIA NO RAILWAY")
    print("=" * 50)
    
    # Lista das variáveis necessárias
    required_vars = {
        'MEDIA_APRESENTACAO': 'Foto de apresentação/start',
        'MEDIA_VIDEO_QUENTE': 'Vídeo principal das prévias',
        'MEDIA_PREVIA_SITE': 'Foto prévia do site',
        'MEDIA_PROVOCATIVA': 'Foto provocativa',
        'MEDIA_VIDEO_SEDUCAO': 'Vídeo de sedução (opcional)'
    }
    
    # Valores corretos esperados (primeiros 20 caracteres)
    expected_values = {
        'MEDIA_APRESENTACAO': 'AgACAgEAAxkDAAICkGif',
        'MEDIA_VIDEO_QUENTE': 'BAACAgEAAxkDAAIOLWin',
        'MEDIA_PREVIA_SITE': 'AgACAgEAAxkDAAIOL2in',
        'MEDIA_PROVOCATIVA': 'AgACAgEAAxkDAAIOMGin',
        'MEDIA_VIDEO_SEDUCAO': 'AgACAgEAAxkDAAIOLmin'
    }
    
    all_ok = True
    missing_vars = []
    
    for var_name, description in required_vars.items():
        value = os.getenv(var_name)
        expected = expected_values.get(var_name, "")
        
        print(f"\n📋 {var_name}:")
        print(f"   Descrição: {description}")
        
        if value:
            preview = value[:20] + "..." if len(value) > 20 else value
            print(f"   ✅ Configurado: {preview}")
            
            # Verifica se começa com o valor esperado
            if expected and value.startswith(expected):
                print(f"   ✅ Valor correto")
            elif expected:
                print(f"   ⚠️  Valor pode estar incorreto")
                print(f"   📝 Esperado começar com: {expected}")
        else:
            print(f"   ❌ NÃO CONFIGURADO!")
            missing_vars.append(var_name)
            all_ok = False
    
    print("\n" + "=" * 50)
    
    if all_ok:
        print("✅ TODAS AS VARIÁVEIS ESTÃO CONFIGURADAS!")
    else:
        print("❌ VARIÁVEIS FALTANDO NO RAILWAY:")
        for var in missing_vars:
            print(f"   - {var}")
        
        print("\n📋 COMANDOS PARA CONFIGURAR NO RAILWAY:")
        print("   1. Acesse: https://railway.app/dashboard")
        print("   2. Selecione o projeto do bot")
        print("   3. Vá em 'Variables'")
        print("   4. Adicione estas variáveis:")
        print()
        
        # Valores completos corretos
        correct_values = {
            'MEDIA_APRESENTACAO': 'AgACAgEAAxkDAAICkGifbTCVRssGewRrBD5ioZ7FHiH7AAISsjEb9OQBRT8IAAFhTPLV2AEAAwIAA3cAAzYE',
            'MEDIA_VIDEO_QUENTE': 'BAACAgEAAxkDAAIOLWinfTqfJ4SEWvCrHda68K9h70KKAAIbBwACMQFBRR_rsl9biH1zNgQ',
            'MEDIA_PREVIA_SITE': 'AgACAgEAAxkDAAIOL2infTsn8XIZPi9hbE1NpNIaKXiMAAIzrTEbMQFBRR63yONsxlHEAQADAgADeQADNgQ',
            'MEDIA_PROVOCATIVA': 'AgACAgEAAxkDAAIOMGinfTyHJB6WxE3A09JJOsfrAonRAAI0rTEbMQFBRVDGNhpvLgs0AQADAgADeQADNgQ',
            'MEDIA_VIDEO_SEDUCAO': 'AgACAgEAAxkDAAIOLminfTr7EFz35tBWIMbepmJyuBDDAAIyrTEbMQFBRYIVHNrbPu82AQADAgADeQADNgQ'
        }
        
        for var in missing_vars:
            if var in correct_values:
                print(f"   {var}={correct_values[var]}")
    
    print("\n🔗 LINKS ÚTEIS:")
    print("   Railway Dashboard: https://railway.app/dashboard")
    print("   Bot Telegram: https://t.me/anacardoso0408_bot")
    print("   Presell: https://presell.ana-cardoso.shop")

if __name__ == "__main__":
    check_media_variables()