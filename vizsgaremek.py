import time
from gpiozero import PWMLED
import Adafruit_DHT
import RPi.GPIO as GPIO
import requests
import datetime
import configparser
import os

# --- Konfigurációs Fájl Beállítások ---
# Meghatározza a konfigurációs fájl elérési útját.
# Az os.path.dirname(os.path.abspath(__file__)) biztosítja, hogy a config.ini ugyanabban a mappában legyen, mint a Python szkript.
CONFIG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'config.ini')

# Globális változók az alkalmazás beállításaihoz.
# Ezeknek a kezdeti értékei (pl. 21, 16, 20) most már csak alapértelmezettek.
# A valós értékeket a load_config() függvény tölti be a config.ini-ből.
DHT_SENSOR = Adafruit_DHT.DHT11 # A DHT szenzor típusa (DHT11 vagy DHT22)
DHT_PIN = 17 # A DHT szenzor adatlábának GPIO pinje. Ezt fixen hagyjuk a kódban.

# Ezeknek a változóknak az értékeit a config.ini-ből töltjük be
TEMP_LIMIT = 20
led_below_limit = 'kék'
led_above_limit = 'piros'
THINGSPEAK_WRITE_API_KEY = ''
THINGSPEAK_USER_API_KEY = ''
THINGSPEAK_CHANNEL_ID = ''

# A GPIO pineket tároló szótár. Kezdeti üres állapot.
# Az értékeket a load_config() tölti fel.
gpio_pins = {} 

# A programban használt LED színek listája.
COLORS = ['piros', 'zöld', 'kék'] 

THINGSPEAK_URL = "https://api.thingspeak.com/update"
THINGSPEAK_DELETE_URL_BASE = "https://api.thingspeak.com/channels/"

# LED példányok tárolására szolgáló szótár.
leds = {}

# --- Konfigurációkezelő Függvények ---

def load_config():
    """Beolvassa a beállításokat a konfigurációs fájlból, vagy alapértelmezetteket használ."""
    global DHT_PIN, TEMP_LIMIT, THINGSPEAK_WRITE_API_KEY, THINGSPEAK_USER_API_KEY, THINGSPEAK_CHANNEL_ID, \
           gpio_pins, led_below_limit, led_above_limit

    config = configparser.ConfigParser()

    if os.path.exists(CONFIG_FILE):
        config.read(CONFIG_FILE)
        print(f"✅ Konfigurációs fájl betöltve: {CONFIG_FILE}")
    else:
        print(f"⚠️ Konfigurációs fájl ({CONFIG_FILE}) nem található. Alapértelmezett értékek használata és mentése.")

    # [GPIO] szekció - getint használatával
    gpio_pins['piros'] = config.getint('GPIO', 'piros', fallback=21)
    gpio_pins['zöld'] = config.getint('GPIO', 'zold', fallback=16) 
    gpio_pins['kék'] = config.getint('GPIO', 'kek', fallback=20)

    # [LED_Behavior] szekció - getint és get használatával
    TEMP_LIMIT = config.getint('LED_Behavior', 'temp_limit', fallback=20)
    led_below_limit = config.get('LED_Behavior', 'led_below_limit', fallback='kék')
    led_above_limit = config.get('LED_Behavior', 'led_above_limit', fallback='piros')

    # [Thingspeak] szekció - get használatával
    THINGSPEAK_WRITE_API_KEY = config.get('Thingspeak', 'write_api_key', fallback='')
    THINGSPEAK_USER_API_KEY = config.get('Thingspeak', 'user_api_key', fallback='')
    THINGSPEAK_CHANNEL_ID = config.get('Thingspeak', 'channel_id', fallback='')

    # Ha a fájl nem létezett, vagy valami hiányzott, most elmentjük az alapértelmezetteket.
    save_config()


def save_config():
    """Elmenti a jelenlegi beállításokat a konfigurációs fájlba."""
    config = configparser.ConfigParser()

    # Létrehozzuk a szekciókat és feltöltjük az aktuális értékekkel
    config['GPIO'] = {
        'piros': str(gpio_pins['piros']),
        'zold': str(gpio_pins['zöld']),
        'kek': str(gpio_pins['kék'])
    }
    config['LED_Behavior'] = {
        'temp_limit': str(TEMP_LIMIT),
        'led_below_limit': led_below_limit,
        'led_above_limit': led_above_limit
    }
    config['Thingspeak'] = {
        'write_api_key': THINGSPEAK_WRITE_API_KEY,
        'user_api_key': THINGSPEAK_USER_API_KEY,
        'channel_id': THINGSPEAK_CHANNEL_ID
    }

    # Beírjuk a konfigurációs fájlba
    try:
        with open(CONFIG_FILE, 'w') as configfile:
            config.write(configfile)
        print(f"✅ Konfiguráció elmentve: {CONFIG_FILE}")
    except IOError as e:
        print(f"❌ Hiba a konfigurációs fájl mentésekor ({CONFIG_FILE}): {e}")


# --- GPIO Beállítások ---
GPIO.setmode(GPIO.BCM)

# --- Segédfüggvények ---

def init_leds():
    """
    Inicializálja a LED-eket a jelenlegi GPIO beállítások alapján, vagy frissíti azokat.
    Ez a függvény felszabadítja az előzőleg foglalt GPIO erőforrásokat és újra létrehozza a LED objektumokat.
    """
    global leds
    # Felszabadítja a korábbi GPIO erőforrásokat, ha már léteznek LED objektumok.
    for led in leds.values():
        if isinstance(led, PWMLED):
            led.close()

    # Újra inicializálja a LED-eket az aktuális gpio_pins beállítások alapján.
    leds = {}
    for color, pin in gpio_pins.items():
        try:
            leds[color] = PWMLED(pin)
        except Exception as e:
            print(f"⚠️ Hiba a {color} LED inicializálásakor a {pin} GPIO-n: {e}")
            print("Kérlek, ellenőrizd, hogy a GPIO pin szabad-e és létezik-e.")
            leds[color] = None

    print("✅ LED-ek inicializálva az új GPIO-kkal.")


def set_led(color):
    """
    Beállítja a megadott színű LED-et (bekapcsolja), a többi LED-et kikapcsolja.
    """
    for led_name, led_object in leds.items():
        if led_object is not None:
            led_object.value = 0

    if color in leds and leds[color] is not None:
        leds[color].value = 1
        print(f"🔔 LED: {color.upper()} ({'<=20°C' if color == led_below_limit else '>20°C'})")
    else:
        print(f"⚠️ Hibás vagy nem inicializált LED szín megadva: {color}")

def send_to_thingspeak(temp, hum):
    """
    Elküldi a hőmérsékletet és páratartalmat a Thingspeak csatornára.
    """
    if not THINGSPEAK_WRITE_API_KEY or not THINGSPEAK_CHANNEL_ID:
        print("❌ Thingspeak API kulcs vagy csatorna ID hiányzik. Adatküldés kihagyva.")
        return

    try:
        payload = {
            'api_key': THINGSPEAK_WRITE_API_KEY,
            'field1': round(temp, 2),
            'field2': round(hum, 2)
        }
        response = requests.get(THINGSPEAK_URL, params=payload)

        if response.status_code == 200:
            print("⬆️ Adatok elküldve Thingspeakre.")
        else:
            print(f"❌ Hiba a Thingspeak küldéskor: HTTP {response.status_code} - {response.text}")
    except requests.exceptions.RequestException as e:
        print(f"⚠️ Hálózati hiba a Thingspeak küldéskor: {e}")

def delete_thingspeak_data(minutes_ago):
    """
    Törli az adatokat a Thingspeak csatornáról egy megadott időintervallumból.
    Ehhez a 'User API Key' szükséges.
    """
    if not THINGSPEAK_USER_API_KEY or not THINGSPEAK_CHANNEL_ID:
        print("❌ Thingspeak User API kulcs vagy csatorna ID hiányzik. Törlés kihagyva.")
        return

    delete_before_date = datetime.datetime.now() - datetime.timedelta(minutes=minutes_ago)

    delete_url = f"{THINGSPEAK_DELETE_URL_BASE}{THINGSPEAK_CHANNEL_ID}/feeds.json"
    params = {
        'api_key': THINGSPEAK_USER_API_KEY,
        'end': delete_before_date.isoformat(sep='T', timespec='seconds') + 'Z'
    }

    print(f"Adatok törlése a {THINGSPEAK_CHANNEL_ID} csatornáról {minutes_ago} perccel ezelőtti időpontig ({delete_before_date.strftime('%Y-%m-%d %H:%M:%S')} előtt).")
    try:
        response = requests.delete(delete_url, params=params)

        if response.status_code == 200:
            print("✅ Adatok sikeresen törölve a Thingspeakről!")
        else:
            print(f"❌ Hiba a Thingspeak törléskor: HTTP {response.status_code} - {response.text}")
            print("Tipp: Ellenőrizd a USER_API_KEY-t, az kell a törléshez!")
    except requests.exceptions.RequestException as e:
        print(f"⚠️ Hálózati hiba a Thingspeak törléskor: {e}")

# --- Konfigurációs Menüpontok ---

def change_gpio_pins():
    """
    Lehetővé teszi a piros, zöld és kék LED-ek GPIO portjainak módosítását.
    A felhasználó egyesével adhatja meg az új GPIO számokat.
    """
    global gpio_pins
    print("\n🎛️ GPIO portok módosítása:")
    for color in COLORS:
        while True:
            try:
                current_pin = gpio_pins.get(color, 'nincs beállítva')
                pin_input = input(f"{color.upper()} LED GPIO (jelenleg {current_pin}): ")
                if pin_input.strip() == '':
                    print(f"⏩ {color.upper()} LED GPIO megtartva: {current_pin}")
                    break
                pin = int(pin_input)
                if 0 <= pin <= 27:
                    gpio_pins[color] = pin
                    break
                else:
                    print("⚠️ Érvénytelen GPIO szám. Kérlek, 0 és 27 közötti számot adj meg.")
            except ValueError:
                print("⚠️ Hibás érték. Kérlek, csak számot adj meg.")
    init_leds()
    save_config()

def change_led_behavior():
    """
    Lehetővé teszi a hőmérséklethez tartozó LED színek beállítását és a hőmérsékleti limit módosítását.
    """
    global led_below_limit, led_above_limit, TEMP_LIMIT
    print(f"\n🎨 LED színek beállítása a hőmérséklet alapján (jelenlegi határ: {TEMP_LIMIT}°C):")

    while True:
        temp_limit_input = input(f"Új hőmérsékleti határ (jelenleg {TEMP_LIMIT}°C, enter a megtartáshoz): ").strip()
        if temp_limit_input == '':
            print(f"⏩ Hőmérsékleti határ megtartva: {TEMP_LIMIT}°C")
            break
        try:
            new_limit = int(temp_limit_input)
            TEMP_LIMIT = new_limit
            break
        except ValueError:
            print("⚠️ Hibás érték. Kérlek, csak számot adj meg.")

    while True:
        below_input = input(f"{TEMP_LIMIT}°C alatt milyen LED szín legyen (piros/zöld/kék, jelenleg: {led_below_limit}, enter a megtartáshoz): ").strip().lower()
        if below_input in COLORS:
            led_below_limit = below_input
            break
        elif below_input == '':
            print("Megtartva a jelenlegi beállítás.")
            break
        else:
            print("⚠️ Hibás szín! Kérlek, válassz a 'piros', 'zöld', 'kék' közül.")

    while True:
        above_input = input(f"{TEMP_LIMIT}°C felett milyen LED szín legyen (piros/zöld/kék, jelenleg: {led_above_limit}, enter a megtartáshoz): ").strip().lower()
        if above_input in COLORS:
            led_above_limit = above_input
            break
        elif above_input == '':
            print("Megtartva a jelenlegi beállítás.")
            break
        else:
            print("⚠️ Hibás szín! Kérlek, válassz a 'piros', 'zöld', 'kék' közül.")

    print(f"✅ Beállítva: <={TEMP_LIMIT}°C ➜ {led_below_limit.upper()}, >{TEMP_LIMIT}°C ➜ {led_above_limit.upper()}")
    save_config()

def change_thingspeak_settings():
    """
    Lehetővé teszi a Thingspeak beállítások (Csatorna ID, Író API kulcs, Felhasználói API kulcs) módosítását.
    """
    global THINGSPEAK_CHANNEL_ID, THINGSPEAK_WRITE_API_KEY, THINGSPEAK_USER_API_KEY
    print("\n☁️ Thingspeak beállítások módosítása:")

    channel_id_input = input(f"Thingspeak csatorna ID (jelenleg '{THINGSPEAK_CHANNEL_ID}', enter a megtartáshoz): ").strip()
    if channel_id_input:
        THINGSPEAK_CHANNEL_ID = channel_id_input

    write_api_key_input = input(f"Thingspeak Író API kulcs (jelenleg '{THINGSPEAK_WRITE_API_KEY}', enter a megtartáshoz): ").strip()
    if write_api_key_input:
        THINGSPEAK_WRITE_API_KEY = write_api_key_input

    user_api_key_input = input(f"Thingspeak Felhasználói API kulcs (jelenleg '{THINGSPEAK_USER_API_KEY}', törléshez szükséges, enter a megtartáshoz): ").strip()
    THINGSPEAK_USER_API_KEY = user_api_key_input # Az üres stringet is mentjük, ha a felhasználó üresen hagyja

    print("✅ Thingspeak beállítások frissítve.")
    save_config()

def perform_thingspeak_data_delete():
    """
    Bekéri a felhasználótól, hogy hány perccel ezelőtti adatokat töröljön, majd végrehajtja a törlést.
    """
    try:
        minutes = int(input("Hány perccel ezelőtti adatokat töröljünk? (pl. 5 perc az utolsó 5 percet törli): "))
        if minutes >= 0:
            delete_thingspeak_data(minutes)
        else:
            print("⚠️ Érvénytelen időtartam, pozitív számot adj meg!")
    except ValueError:
        print("⚠️ Hibás érték, csak számot adj meg!")

# --- Fő Működési Ciklus ---

def run_sensor_loop_and_thingspeak():
    """
    Ez a fő működési ciklus, ami folyamatosan olvassa a szenzor adatait,
    vezérli a LED-eket és küldi az adatokat a Thingspeakre.
    """
    print("\n▶️ Rendszer indítása... Nyomj CTRL+C-t a kilépéshez.")

    # Átlagoláshoz szükséges beállítások
    NUM_READINGS = 5 # Ennyi mérést veszünk figyelembe az átlagoláshoz
    READING_INTERVAL = 2 # Másodperc a mérések között (2 * 5 = 10 másodperc mérés)
    THINGSPEAK_SEND_INTERVAL = 15 # Másodperc a Thingspeak küldések között (API limit miatt)

    try:
        last_thingspeak_send_time = time.time() - THINGSPEAK_SEND_INTERVAL # Azonnali küldés indításkor

        while True:
            # --- Adatok gyűjtése és átlagolása ---
            valid_temps = []
            valid_hums = []

            print(f"Adatok gyűjtése ({NUM_READINGS} mérés)...")
            for i in range(NUM_READINGS):
                humidity, temp = Adafruit_DHT.read_retry(DHT_SENSOR, DHT_PIN)
                if temp is not None and humidity is not None:
                    valid_temps.append(temp)
                    valid_hums.append(humidity)
                    # print(f"  Mérés {i+1}: Hőm={temp:.1f}°C, Pár={humidity:.1f}%") # Ezt kikapcsolhatod, ha túl sok infó
                else:
                    print(f"  Mérés {i+1}: ❌ Szenzorhiba! Nincs adat.")
                time.sleep(READING_INTERVAL)

            if valid_temps and valid_hums:
                avg_temp = sum(valid_temps) / len(valid_temps)
                avg_hum = sum(valid_hums) / len(valid_hums)

                print(f"\n🌡️ Átlag Hőmérséklet: {avg_temp:.1f}°C, 💧 Átlag Páratartalom: {avg_hum:.1f}%")

                # LED beállítása az átlag hőmérséklet alapján.
                if avg_temp <= TEMP_LIMIT:
                    set_led(led_below_limit)
                else:
                    set_led(led_above_limit)

                # Adatok küldése Thingspeakre, csak ha eltelt a szükséges idő
                if (time.time() - last_thingspeak_send_time) >= THINGSPEAK_SEND_INTERVAL:
                    send_to_thingspeak(avg_temp, avg_hum)
                    last_thingspeak_send_time = time.time()
                else:
                    remaining_time = THINGSPEAK_SEND_INTERVAL - (time.time() - last_thingspeak_send_time)
                    print(f"⏳ Thingspeak küldés kihagyva, {remaining_time:.0f} másodperc múlva esedékes.")

            else:
                print("❌ Nem sikerült elegendő adatot gyűjteni a szenzorról. Ellenőrizd a bekötést!")
                for led_object in leds.values():
                    if led_object is not None:
                        led_object.value = 0 # Minden LED kikapcsolása hiba esetén.

            # Nincs szükség extra time.sleep() itt, mert az átlagolás már beépítette a várakozást.
            # A Thingspeak küldés intervalluma adja a ritmust.

    except KeyboardInterrupt:
        print("\n🛑 Kilépés a ciklusból...")
    except Exception as e:
        print(f"Hiba történt a futás közben: {e}")
    finally:
        GPIO.cleanup()
        for led_object in leds.values():
            if led_object is not None:
                led_object.close()
        print("GPIO erőforrások felszabadítva.")


# --- Főmenü ---

def main_menu():
    """
    Megjeleníti a főmenüt és kezeli a felhasználói interakciókat.
    Ez a program belépési pontja.
    """
    load_config() # Ezzel töltjük be először a beállításokat a config.ini-ből
    init_leds() # Ez inicializálja a LED-eket a beolvasott pinekkel
    while True:
        print("\n--- SmartTempHub Főmenü ---")
        print("1. GPIO portok módosítása")
        print("2. LED színek beállítása hőmérséklet alapján")
        print("3. Thingspeak beállítások módosítása")
        print("4. Thingspeak adatok törlése (időalapú)")
        print("5. Rendszer indítása (Szenzor + LED + Thingspeak)")
        print("6. Kilépés")

        choice = input("Válasszon (1-6): ").strip()

        if choice == '1':
            change_gpio_pins()
        elif choice == '2':
            change_led_behavior()
        elif choice == '3':
            change_thingspeak_settings()
        elif choice == '4':
            perform_thingspeak_data_delete()
        elif choice == '5':
            run_sensor_loop_and_thingspeak()
            # Ha a futás befejeződött (pl. CTRL+C miatt), visszatér a főmenübe.
            # Ekkor újra inicializáljuk a LED-eket, hogy a menüből visszatérve is működjenek.
            init_leds()
        elif choice == '6':
            print("👋 Kilépés a programból...")
            GPIO.cleanup()
            for led_object in leds.values():
                if led_object is not None:
                    led_object.close()
            break
        else:
            print("❌ Érvénytelen választás. Kérlek, válassz 1 és 6 között.")

# A program indítása a főmenü meghívásával, amikor a szkriptet közvetlenül futtatják.
if __name__ == "__main__":
    main_menu()
