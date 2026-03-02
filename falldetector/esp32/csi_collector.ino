/**
 * ESP32 CSI Collector for Fall Detection System
 * 
 * Collects WiFi Channel State Information and transmits via USB serial.
 * Works with the WiFi Fall Detector calibration and detection system.
 * 
 * Hardware: ESP32 (NodeMCU, TTGO, or similar)
 * Baud Rate: 115200 (can be changed)
 * 
 * Packet Format (binary):
 *   [0xAA][0x55][TYPE][TIMESTAMP(4)][RSSI][CH][AMP(208)][PHASE(208)][CHECKSUM]
 */

#include <Arduino.h>
#include <WiFi.h>
#include <esp_wifi.h>

// ==================== CONFIGURATION ====================
const char* ROUTER_SSID = "YOUR_WIFI_SSID";
const char* ROUTER_PASSWORD = "YOUR_WIFI_PASSWORD";

#define SERIAL_BAUD_RATE 115200
#define CSI_SUBCARRIERS 64      // Hardware subcarriers
#define OUTPUT_SUBCARRIERS 104  // Output format (padded)

// ==================== GLOBALS ====================
bool connected = false;
uint32_t csiCount = 0;
uint32_t packetSeq = 0;

// Packet types
#define PKT_TYPE_CSI     0x01
#define PKT_TYPE_STATUS  0x02
#define PKT_TYPE_HEARTBEAT 0x03

// ==================== CSI CALLBACK ====================
void wifi_csi_cb(void *ctx, wifi_csi_info_t *data) {
    if (!data) return;
    
    csiCount++;
    
    int8_t *csi_ptr = data->buf;
    uint16_t csi_len = data->len;
    int num_subcarriers = csi_len / 2;
    
    // Prepare amplitude array (104 values, zero-padded)
    int16_t amplitude[OUTPUT_SUBCARRIERS];
    int16_t phase[OUTPUT_SUBCARRIERS];
    memset(amplitude, 0, sizeof(amplitude));
    memset(phase, 0, sizeof(phase));
    
    // Extract CSI from first 64 subcarriers
    for (int i = 0; i < num_subcarriers && i < CSI_SUBCARRIERS; i++) {
        int8_t real = csi_ptr[i * 2];
        int8_t imag = csi_ptr[i * 2 + 1];
        
        // Amplitude: sqrt(I² + Q²) * 10 for scaling
        amplitude[i] = (int16_t)sqrt((float)real * real + (float)imag * imag) * 10;
        
        // Phase: atan2(Q, I) * 1000 for precision
        phase[i] = (int16_t)(atan2((float)imag, (float)real) * 1000);
    }
    
    // Send binary packet
    Serial.write(0xAA);
    Serial.write(0x55);
    Serial.write(PKT_TYPE_CSI);
    
    // Sequence number (4 bytes)
    Serial.write((uint8_t)(packetSeq & 0xFF));
    Serial.write((uint8_t)((packetSeq >> 8) & 0xFF));
    Serial.write((uint8_t)((packetSeq >> 16) & 0xFF));
    Serial.write((uint8_t)((packetSeq >> 24) & 0xFF));
    packetSeq++;
    
    // Timestamp (4 bytes)
    uint32_t timestamp = micros();
    Serial.write((uint8_t)(timestamp & 0xFF));
    Serial.write((uint8_t)((timestamp >> 8) & 0xFF));
    Serial.write((uint8_t)((timestamp >> 16) & 0xFF));
    Serial.write((uint8_t)((timestamp >> 24) & 0xFF));
    
    // RSSI (1 byte, signed)
    Serial.write((uint8_t)data->rx_ctrl.rssi);
    
    // Channel (1 byte)
    Serial.write(data->rx_ctrl.channel);
    
    // Amplitude (104 * 2 bytes)
    for (int i = 0; i < OUTPUT_SUBCARRIERS; i++) {
        Serial.write((uint8_t)(amplitude[i] & 0xFF));
        Serial.write((uint8_t)((amplitude[i] >> 8) & 0xFF));
    }
    
    // Phase (104 * 2 bytes)
    for (int i = 0; i < OUTPUT_SUBCARRIERS; i++) {
        Serial.write((uint8_t)(phase[i] & 0xFF));
        Serial.write((uint8_t)((phase[i] >> 8) & 0xFF));
    }
    
    // Checksum (XOR of all bytes)
    uint8_t checksum = 0;
    checksum ^= PKT_TYPE_CSI;
    for (int i = 0; i < 4; i++) checksum ^= ((uint8_t*)(&packetSeq))[i];
    for (int i = 0; i < 4; i++) checksum ^= ((uint8_t*)(&timestamp))[i];
    checksum ^= (uint8_t)data->rx_ctrl.rssi;
    checksum ^= data->rx_ctrl.channel;
    for (int i = 0; i < OUTPUT_SUBCARRIERS * 2; i++) {
        checksum ^= ((uint8_t*)amplitude)[i];
    }
    Serial.write(checksum);
}

// ==================== SETUP ====================
void setup() {
    Serial.begin(SERIAL_BAUD_RATE);
    delay(1000);
    
    // Send startup message (text, not binary)
    Serial.println();
    Serial.println("========================================");
    Serial.println("  ESP32 CSI Fall Detector v2.0");
    Serial.println("========================================");
    Serial.println();
    
    // WiFi setup
    WiFi.mode(WIFI_STA);
    Serial.print("Connecting to: ");
    Serial.println(ROUTER_SSID);
    
    WiFi.begin(ROUTER_SSID, ROUTER_PASSWORD);
    
    int attempts = 0;
    while (WiFi.status() != WL_CONNECTED && attempts < 30) {
        delay(500);
        Serial.print(".");
        attempts++;
    }
    
    if (WiFi.status() == WL_CONNECTED) {
        connected = true;
        Serial.println();
        Serial.print("Connected! IP: ");
        Serial.println(WiFi.localIP());
        Serial.print("Channel: ");
        Serial.println(WiFi.channel());
    } else {
        Serial.println();
        Serial.println("WiFi failed - passive mode only");
        connected = false;
    }
    
    // Enable CSI
    wifi_csi_config_t csi_config = {
        .lltf_en = true,
        .htltf_en = true,
        .stbc_htltf2_en = true,
        .ltf_merge_en = true,
        .channel_filter_en = false,
        .manu_scale = false,
        .shift = 0,
    };
    
    esp_wifi_set_csi(true);
    esp_wifi_set_csi_config(&csi_config);
    esp_wifi_set_csi_rx_cb(&wifi_csi_cb, NULL);
    
    Serial.println("CSI collection enabled");
    Serial.println();
    Serial.println("Ready for calibration/detection!");
    Serial.println();
    
    // Send status packet
    Serial.write(0xAA);
    Serial.write(0x55);
    Serial.write(PKT_TYPE_STATUS);
    Serial.write(connected ? 0x01 : 0x00);
    Serial.write(WiFi.channel());
}

// ==================== LOOP ====================
void loop() {
    static unsigned long lastHeartbeat = 0;
    
    // Heartbeat every 5 seconds
    if (millis() - lastHeartbeat > 5000) {
        lastHeartbeat = millis();
        
        Serial.write(0xAA);
        Serial.write(0x55);
        Serial.write(PKT_TYPE_HEARTBEAT);
        
        // CSI count (4 bytes)
        Serial.write((uint8_t)(csiCount & 0xFF));
        Serial.write((uint8_t)((csiCount >> 8) & 0xFF));
        Serial.write((uint8_t)((csiCount >> 16) & 0xFF));
        Serial.write((uint8_t)((csiCount >> 24) & 0xFF));
        
        Serial.write(connected ? 0x01 : 0x00);
    }
    
    // Handle serial commands
    if (Serial.available() > 0) {
        char cmd = Serial.read();
        switch (cmd) {
            case 'S':  // Status
                Serial.write(0xAA);
                Serial.write(0x55);
                Serial.write(PKT_TYPE_STATUS);
                Serial.write(connected ? 0x01 : 0x00);
                Serial.write(WiFi.channel());
                break;
            case 'R':  // Reset counter
                csiCount = 0;
                break;
            case 'C':  // Reconnect WiFi
                WiFi.reconnect();
                break;
        }
    }
    
    delay(1);
}
