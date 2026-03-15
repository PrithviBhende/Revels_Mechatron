/*
 * ESP32 LED Floor Controller - WORKING ARCHITECTURE
 * TCP Server mode with WS2812B LED strips
 * Compatible with the working Python code
 */

#include <WiFi.h>
#include <ESPmDNS.h>
#include <Adafruit_NeoPixel.h>

// ==================== WiFi Configuration ====================
const char* ssid = "TP-LINK_5C4A";
const char* password = "86124560";          // Replace with your password

// ==================== TCP Server ====================
WiFiServer server(8080);
WiFiClient client;

// ==================== LED Configuration ====================
// GPIO pins for 4 LED strips (one per tile)
const int LED_PINS[4] = {12, 13, 14, 27};    // Adjust based on your wiring

// Number of LEDs per strip
const int LEDS_PER_STRIP = 180;              // Adjust if different

// LED strips
Adafruit_NeoPixel* strips[4];

// Current colors for each strip
struct StripState {
  uint8_t r;
  uint8_t g;
  uint8_t b;
  bool on;
};
StripState stripStates[4];

// ==================== Setup ====================
void setup() {
  Serial.begin(115200);
  delay(1000);
  
  Serial.println("\n================================");
  Serial.println("ESP32 LED Floor Controller");
  Serial.println("WS2812B + TCP Server Mode");
  Serial.println("================================\n");
  
  // Initialize LED strips
  for (int i = 0; i < 4; i++) {
    strips[i] = new Adafruit_NeoPixel(LEDS_PER_STRIP, LED_PINS[i], NEO_GRB + NEO_KHZ800);
    strips[i]->begin();
    strips[i]->show();  // Initialize all pixels to 'off'
    
    stripStates[i].r = 0;
    stripStates[i].g = 0;
    stripStates[i].b = 0;
    stripStates[i].on = false;
  }
  
  Serial.println("✅ LED strips initialized");
  Serial.print("   Pins: ");
  for (int i = 0; i < 4; i++) {
    Serial.print(LED_PINS[i]);
    if (i < 3) Serial.print(", ");
  }
  Serial.println();
  
  // Connect to WiFi
  WiFi.mode(WIFI_STA);
  WiFi.begin(ssid, password);
  
  Serial.print("Connecting to WiFi");
  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
    Serial.print(".");
  }
  
  Serial.println("\n✅ WiFi connected!");
  Serial.print("   IP address: ");
  Serial.println(WiFi.localIP());
  
  // Get MAC address without colons
  String mac = WiFi.macAddress();
  mac.replace(":", "");
  Serial.print("   MAC Address: ");
  Serial.println(mac);
  
  // Blink all strips blue 3 times to confirm WiFi connection
  Serial.println("💙 Blinking blue to confirm WiFi...");
  for (int blink = 0; blink < 3; blink++) {
    setAllStrips(0, 0, 255);
    delay(500);
    setAllStrips(0, 0, 0);
    delay(500);
  }
  
  // Start mDNS
  String hostname = "esp-" + mac;
  if (MDNS.begin(hostname.c_str())) {
    Serial.print("✅ mDNS responder started: ");
    Serial.println(hostname + ".local");
  } else {
    Serial.println("❌ mDNS failed to start");
  }
  
  // Start TCP server
  server.begin();
  Serial.println("✅ TCP Server started on port 8080");
  Serial.println("\n🎯 Ready for connections!");
  Serial.println("   Hostname: " + hostname + ".local:8080\n");
}

// ==================== Main Loop ====================
void loop() {
  // Check for new client
  if (!client || !client.connected()) {
    client = server.available();
    if (client) {
      Serial.println("📡 Client connected");
      Serial.print("   From: ");
      Serial.println(client.remoteIP());
    }
  }
  
  // Handle client commands
  if (client && client.available()) {
    String cmd = client.readStringUntil('\n');
    cmd.trim();
    
    if (cmd.length() > 0) {
      Serial.print("📥 Received: ");
      Serial.println(cmd);
      processCommand(cmd);
    }
  }
  
  delay(10);
}

// ==================== Command Processing ====================
void processCommand(String cmd) {
  // Command formats:
  // T1_ON, T2_OFF, T3_ON, T4_OFF           - Simple ON/OFF
  // T1_COLOR_255_0_0                        - Set specific color
  // T1_TOGGLE                               - Toggle state
  
  if (!cmd.startsWith("T") || cmd.length() < 5) {
    Serial.println("⚠️  Invalid command format");
    return;
  }
  
  // Parse tile number (T1 -> index 0, T2 -> index 1, etc.)
  int tileNum = cmd.charAt(1) - '1';  // Convert '1'-'4' to 0-3
  
  if (tileNum < 0 || tileNum >= 4) {
    Serial.println("⚠️  Invalid tile number");
    return;
  }
  
  // Parse command type
  String action = cmd.substring(3);  // Skip "T1_"
  
  if (action == "ON") {
    // Turn on with default color (green) or last used color
    if (stripStates[tileNum].r == 0 && stripStates[tileNum].g == 0 && stripStates[tileNum].b == 0) {
      setStrip(tileNum, 0, 255, 0);  // Default green
    } else {
      setStrip(tileNum, stripStates[tileNum].r, stripStates[tileNum].g, stripStates[tileNum].b);
    }
    Serial.print("💡 Tile ");
    Serial.print(tileNum + 1);
    Serial.println(" ON");
    
  } else if (action == "OFF") {
    // Turn off
    setStrip(tileNum, 0, 0, 0);
    stripStates[tileNum].on = false;
    Serial.print("⚫ Tile ");
    Serial.print(tileNum + 1);
    Serial.println(" OFF");
    
  } else if (action == "TOGGLE") {
    // Toggle state
    if (stripStates[tileNum].on) {
      setStrip(tileNum, 0, 0, 0);
      stripStates[tileNum].on = false;
      Serial.print("⚫ Tile ");
      Serial.print(tileNum + 1);
      Serial.println(" toggled OFF");
    } else {
      if (stripStates[tileNum].r == 0 && stripStates[tileNum].g == 0 && stripStates[tileNum].b == 0) {
        setStrip(tileNum, 0, 255, 0);  // Default green
      } else {
        setStrip(tileNum, stripStates[tileNum].r, stripStates[tileNum].g, stripStates[tileNum].b);
      }
      Serial.print("💡 Tile ");
      Serial.print(tileNum + 1);
      Serial.println(" toggled ON");
    }
    
  } else if (action.startsWith("COLOR_")) {
    // Parse color: COLOR_R_G_B
    int firstUnderscore = action.indexOf('_');
    int secondUnderscore = action.indexOf('_', firstUnderscore + 1);
    int thirdUnderscore = action.indexOf('_', secondUnderscore + 1);
    
    if (firstUnderscore != -1 && secondUnderscore != -1 && thirdUnderscore != -1) {
      uint8_t r = action.substring(firstUnderscore + 1, secondUnderscore).toInt();
      uint8_t g = action.substring(secondUnderscore + 1, thirdUnderscore).toInt();
      uint8_t b = action.substring(thirdUnderscore + 1).toInt();
      
      setStrip(tileNum, r, g, b);
      
      Serial.print("🎨 Tile ");
      Serial.print(tileNum + 1);
      Serial.print(" set to RGB(");
      Serial.print(r);
      Serial.print(",");
      Serial.print(g);
      Serial.print(",");
      Serial.print(b);
      Serial.println(")");
    } else {
      Serial.println("⚠️  Invalid color format");
    }
    
  } else {
    Serial.println("⚠️  Unknown command: " + action);
  }
}

// ==================== LED Control Functions ====================
void setStrip(int stripNum, uint8_t r, uint8_t g, uint8_t b) {
  if (stripNum < 0 || stripNum >= 4) return;
  
  // Update state
  stripStates[stripNum].r = r;
  stripStates[stripNum].g = g;
  stripStates[stripNum].b = b;
  stripStates[stripNum].on = (r > 0 || g > 0 || b > 0);
  
  // Set all pixels in this strip
  uint32_t color = strips[stripNum]->Color(r, g, b);
  for (int i = 0; i < LEDS_PER_STRIP; i++) {
    strips[stripNum]->setPixelColor(i, color);
  }
  strips[stripNum]->show();
}

void setAllStrips(uint8_t r, uint8_t g, uint8_t b) {
  for (int i = 0; i < 4; i++) {
    setStrip(i, r, g, b);
  }
}
