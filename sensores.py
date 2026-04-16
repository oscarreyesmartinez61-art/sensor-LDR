from machine import Pin, ADC, mem32
from machine import Timer
import time

########################## REGISTROS GPIO ESP32
GPIO_OUT_W1TS = 0x3FF44008
GPIO_OUT_W1TC = 0x3FF4400C

def led_on(pin):
    mem32[GPIO_OUT_W1TS] = (1 << pin)

def led_off(pin):
    mem32[GPIO_OUT_W1TC] = (1 << pin)

###########################

timer = Timer(0)

# VARIABLES GLOBALES
filtro_promedio = False
filtro_mediana = False
filtro_exponencial = False

buffer_dato = None
dato_nuevo = False

sensor = ADC(Pin(34))
sensor.width(ADC.WIDTH_12BIT)
sensor.atten(ADC.ATTN_11DB)

archivo = open("datos_adc.csv", "w")
archivo.write("Crudo,Promedio,Mediana,Exponencial\n")

btn_frec = Pin(25, Pin.IN, Pin.PULL_UP)
btn_filtros = Pin(26, Pin.IN, Pin.PULL_UP)

Pin(2, Pin.OUT)
LED_VERDE = 2

##############################
# FILTROS

def filtro_mediana_func(valor, n=5):
    lecturas = [valor]
    for _ in range(n-1):
        lecturas.append(sensor.read())
    lecturas.sort()
    return lecturas[n // 2]

def filtro_promedio_func(valor, n=5):
    suma = valor
    for _ in range(n-1):
        suma += sensor.read()
    return suma // n

alpha = 0.2
valor_exponencial = sensor.read()

def filtro_exponencial_func(nueva_lectura):
    global valor_exponencial
    valor_exponencial = alpha * nueva_lectura + (1 - alpha) * valor_exponencial
    return int(valor_exponencial)

def configurar_filtros():
    global filtro_promedio, filtro_mediana, filtro_exponencial

    print("Activar filtros? (1=Si 0=No)")
    filtro_promedio = int(input("Filtro promedio: ")) == 1
    filtro_mediana = int(input("Filtro mediana: ")) == 1
    filtro_exponencial = int(input("Filtro exponencial: ")) == 1

##########################

# INTERRUPCIONES BOTONES
dato_requested = False
_last_dato_irq = 0
AUTO_IRQ_DEBOUNCE_MS = 300

def _dato_irq_handler(pin):
    global dato_requested, _last_dato_irq
    now = time.ticks_ms()
    if time.ticks_diff(now, _last_dato_irq) > AUTO_IRQ_DEBOUNCE_MS:
        _last_dato_irq = now
        dato_requested = True

btn_frec.irq(trigger=Pin.IRQ_FALLING, handler=_dato_irq_handler)

filtros_requested = False
_last_filtros_irq = 0

def _filtros_irq_handler(pin):
    global filtros_requested, _last_filtros_irq
    now = time.ticks_ms()
    if time.ticks_diff(now, _last_filtros_irq) > AUTO_IRQ_DEBOUNCE_MS:
        _last_filtros_irq = now
        filtros_requested = True

btn_filtros.irq(trigger=Pin.IRQ_FALLING, handler=_filtros_irq_handler)

##########################
# TIMER SOLO LEE ADC

def lectura(timer):
    global buffer_dato, dato_nuevo
    buffer_dato = sensor.read()
    dato_nuevo = True

##########################
# CONFIGURACION INICIAL

frecuencia_consola = int(input("Ingresar Frecuencia Deseada"))
f = frecuencia_consola

configurar_filtros()

print("Crudo Promedio Mediana Exponencial")

timer.init(period=int(1000/f), mode=Timer.PERIODIC, callback=lectura)

##########################
# LOOP PRINCIPAL

while True:

    if dato_nuevo:

        dato_nuevo = False
        valor_crudo = buffer_dato

        promedio = valor_crudo
        mediana = valor_crudo
        exponencial = valor_crudo

        if filtro_promedio:
            promedio = filtro_promedio_func(valor_crudo)

        if filtro_mediana:
            mediana = filtro_mediana_func(valor_crudo)

        if filtro_exponencial:
            exponencial = filtro_exponencial_func(valor_crudo)

        print(valor_crudo, promedio, mediana, exponencial)

        linea = "{},{},{},{}\n".format(valor_crudo, promedio, mediana, exponencial)
        archivo.write(linea)

        mini = 32
        maxi = 2800

        if mini <= valor_crudo <= maxi:
            led_on(LED_VERDE)
        else:
            led_off(LED_VERDE)

    if dato_requested:

        dato_requested = False

        timer.deinit()

        nueva_f = int(input("Ingresar nueva frecuencia: "))
        f = nueva_f

        timer.init(period=int(1000/f), mode=Timer.PERIODIC, callback=lectura)

    if filtros_requested:

        filtros_requested = False

        timer.deinit()

        configurar_filtros()

        timer.init(period=int(1000/f), mode=Timer.PERIODIC, callback=lectura)