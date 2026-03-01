/**
 * ESP32 CSI Collector for Fall Detection System
 * Based on ESP32-CSI-Tool by Steven M. Hernandez
 * 
 * This firmware extracts Channel State Information (CSI) from WiFi signals
 * and sends them via USB serial to the Jetson Nano for processing.
 * 
 * Hardware: ESP32 (NodeMCU, TTGO T8, or similar)
 * Connections: USB to Jetson Nano
 */

#include <Arduino.h>
#include <WiFi.h>
#include <esp_wifi.h>

// Configuration
const char* ROUTER_SSID = "eternacupnoodle";      // Replace with your router SSID
const char* ROUTER_PASSWORD = "semogasuksesamin"; // Replace with your router password

// CSI Configuration
#define CSI_BUFFER_SIZE 512
#define CSI_SUBCARRIERS 64  // Number of CSI subcarriers (typically 64 for 20MHz)

// Serial Configuration
#define SERIAL_BAUD_RATE 921600  // High baud rate for real-time CSI streaming

// Global variables
bool connected = false;
unsigned long lastCsiTime = 0;
uint32_t csiCount = 0;

// CSI data structure
typedef struct {
    int16_t amplitude[CSI_SUBCARRIERS];
    int16_t phase[CSI_SUBCARRIERS];
    uint32_t timestamp;
    int8_t rssi;
    uint8_t channel;
} CSIData;

// CSI callback function
void wifi_csi_cb(void *ctx, wifi_csi_info_t *data) {
    if (!data) return;
    
    csiCount++;
    
    // Get CSI data pointer
    int8_t *csi_ptr = data->buf;
    uint16_t csi_len = data->len;
    
    // Calculate number of subcarriers
    int num_subcarriers = csi_len / 2;  // Each subcarrier has I and Q components
    
    // Prepare data packet
    CSIData csi_data;
    csi_data.timestamp = micros();
    csi_data.rssi = data->rx_ctrl.rssi;
    csi_data.channel = data->rx_ctrl.channel;
    
    // Extract amplitude and phase from CSI
    // CSI data format: Interleaved I (real) and Q (imaginary) components
    for (int i = 0; i < num_subcarriers && i < CSI_SUBCARRIERS; i++) {
        int8_t real = csi_ptr[i * 2];
        int8_t imag = csi_ptr[i * 2 + 1];
        
        // Calculate amplitude: sqrt(real^2 + imag^2)
        csi_data.amplitude[i] = (int16_t)sqrt((float)real * real + (float)imag * imag) * 10;
        
        // Calculate phase: atan2(imag, real)
        csi_data.phase[i] = (int16_t)(atan2((float)imag, (float)real) * 1000);  // Scale for integer transmission
    }
    
    // Send data via serial in binary format
    // Packet format: [HEADER][TIMESTAMP][RSSI][CHANNEL][AMPLITUDE_DATA][PHASE_DATA]
    Serial.write(0xAA);  // Header byte 1
    Serial.write(0x55);  // Header byte 2
    Serial.write(0x01);  // Packet type: CSI data
    
    // Send timestamp (4 bytes)
    Serial.write((uint8_t)(csi_data.timestamp & 0xFF));
    Serial.write((uint8_t)((csi_data.timestamp >> 8) & 0xFF));
    Serial.write((uint8_t)((csi_data.timestamp >> 16) & 0xFF));
    Serial.write((uint8_t)((csi_data.timestamp >> 24) & 0xFF));
    
    // Send RSSI and channel
    Serial.write((uint8_t)csi_data.rssi);
    Serial.write(csi_data.channel);
    
    // Send amplitude data
    for (int i = 0; i < CSI_SUBCARRIERS; i++) {
        Serial.write((uint8_t)(csi_data.amplitude[i] & 0xFF));
        Serial.write((uint8_t)((csi_data.amplitude[i] >> 8) & 0xFF));
    }
    
    // Send phase data
    for (int i = 0; i < CSI_SUBCARRIERS; i++) {
        Serial.write((uint8_t)(csi_data.phase[i] & 0xFF));
        Serial.write((uint8_t)((csi_data.phase[i] >> 8) & 0xFF));
    }
    
    // Send checksum
    uint8_t checksum = 0;
    checksum ^= 0x01;  // Packet type
    for (int i = 0; i < 4; i++) checksum ^= ((uint8_t*)&csi_data.timestamp)[i];
    checksum ^= (uint8_t)csi_data.rssi;
    checksum ^= csi_data.channel;
    for (int i = 0; i < CSI_SUBCARRIERS * 2; i++) {
        checksum ^= ((uint8_t*)csi_data.amplitude)[i];
    }
    Serial.write(checksum);
}

void setup() {
    // Initialize serial
    Serial.begin(SERIAL_BAUD_RATE);
    delay(1000);
    
    Serial.println("\n\n=== ESP32 CSI Fall Detection System ===");
    Serial.println("Initializing...");
    
    // Set WiFi to station mode
    WiFi.mode(WIFI_STA);
    Serial.println("WiFi mode set to STA");
    
    // Configure WiFi for CSI collection
    esp_wifi_set_config(WIFI_IF_STA, &(wifi_config_t){
        .sta = {
            .ssid = ROUTER_SSID,
            .password = ROUTER_PASSWORD,
            .channel = 0,  // Auto channel
            .listen_interval = 10,
        }
    });
    
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
    
    // Connect to router (acting as CSI transmitter)
    Serial.print("Connecting to router: ");
    Serial.println(ROUTER_SSID);
    
    WiFi.begin(ROUTER_SSID, ROUTER_PASSWORD);
    
    int attempts = 0;
    while (WiFi.status() != WL_CONNECTED && attempts < 20) {
        delay(500);
        Serial.print(".");
        attempts++;
    }
    
    if (WiFi.status() == WL_CONNECTED) {
        connected = true;
        Serial.println("\nConnected to router!");
        Serial.print("IP Address: ");
        Serial.println(WiFi.localIP());
        Serial.print("Channel: ");
        Serial.println(WiFi.channel());
        Serial.println("\nCSI collection started. Send data to Jetson Nano...");
    } else {
        Serial.println("\nFailed to connect. Running in passive mode...");
        // Even without connection, we can still collect CSI from nearby WiFi activity
        connected = false;
    }
    
    // Send initialization complete packet
    Serial.write(0xAA);
    Serial.write(0x55);
    Serial.write(0x02);  // Packet type: System status
    Serial.write(connected ? 0x01 : 0x00);  // Connection status
    Serial.write((uint8_t)WiFi.channel());
}

void loop() {
    // Main loop - CSI is collected via callback
    
    // Send heartbeat every 5 seconds
    static unsigned long lastHeartbeat = 0;
    if (millis() - lastHeartbeat > 5000) {
        lastHeartbeat = millis();
        
        // Send heartbeat packet
        Serial.write(0xAA);
        Serial.write(0x55);
        Serial.write(0x03);  // Packet type: Heartbeat
        Serial.write((uint8_t)(csiCount & 0xFF));
        Serial.write((uint8_t)((csiCount >> 8) & 0xFF));
        Serial.write((uint8_t)((csiCount >> 16) & 0xFF));
        Serial.write((uint8_t)((csiCount >> 24) & 0xFF));
        Serial.write(connected ? 0x01 : 0x00);
    }
    
    // Check for serial commands from Jetson Nano
    if (Serial.available() > 0) {
        char cmd = Serial.read();
        switch (cmd) {
            case 'S':  // Status request
                Serial.write(0xAA);
                Serial.write(0x55);
                Serial.write(0x02);
                Serial.write(connected ? 0x01 : 0x00);
                Serial.write((uint8_t)WiFi.channel());
                break;
            case 'R':  // Reset CSI counter
                csiCount = 0;
                Serial.println("CSI counter reset");
                break;
            case 'C':  // Reconnect
                WiFi.reconnect();
                break;
        }
    }
    
    delay(1);
}
