import os
from datetime import datetime

import webbrowser

import re

from threading import Timer
import pywinstyles

import tkinter as tk
import customtkinter as ctk
from CTkMessagebox import CTkMessagebox
from customtkinter import set_default_color_theme

import csv
import threading
import time

import ctypes
import webbrowser

import PIL
from PIL import Image

from Phidget22.Phidget import *
from Phidget22.Devices.VoltageRatioInput import *

# from functools import partial


# Calibration flag
calibrated = False

offset = 0

class MovingAverageFilter:
    def __init__(self, window_size):
        self.window_size = window_size
        self.values = []

    def add_value(self, value):
        self.values.append(value)
        if len(self.values) > self.window_size:
            self.values.pop(0)

    def get_smoothed_value(self):
        if not self.values:
            return None
        return sum(self.values) / len(self.values)

class MyInterface:
    def __init__(self, master):
        self.master = master
        self.master.title("ISO Trainer")

        # Offsets for each channel
        self.offset_channel_0 = 0.0
        self.offset_channel_1 = 0.0

        # Initialize voltageRatioInput
        self.voltageRatioInput0 = None
        self.voltageRatioInput1 = None

        # Connection Flag
        self.connected_flag = False

        # Calibration flags for each channel
        self.calibrated_channel_0 = False
        self.calibrated_channel_1 = False

        # Gains for each channel (populated in connect_phidget)
        self.gain_channel_0 = None
        self.gain_channel_1 = None

        # Initialize multiplier storage
        self.multipliers_dict = {}  # Stores {Equipment: Multiplier}
        self.current_multiplier = 1.0  # Default multiplier

        # Load multiplier data from CSV
        current_directory = os.path.dirname(os.path.abspath("ISO-Trainer.py"))
        data_eq = os.path.join(current_directory, "equipment-data", "equipment.csv")
        self.multiplier_values, self.multipliers_dict = self.load_multiplier_options(data_eq)


        self.logging_active = False  # Flag to indicate whether logging is active

        self.live_update_flag = True  # Flag to control live update thread

        # Folder where the calibration data CSV files are stored
        calibration_folder = "calibration-data"

        # Get list of all files in the folder
        all_files = os.listdir(calibration_folder)

        # Filter only CSV files
        self.calibration_data = [os.path.splitext(file)[0] for file in all_files if file.endswith(".csv")]


        set_default_color_theme("dark-blue")
        ctk.set_appearance_mode("dark")

        self.setup_ui()

    
    def setup_ui(self):
        
        image = PIL.Image.open("images/background_image.png")
        background_image = ctk.CTkImage(image, size=(540, 960))
        # Create a bg label
        bg_lbl = ctk.CTkLabel(self.master, text="", image=background_image)
        bg_lbl.place(x=0, y=0)



        # Header Frame
        header_frame = ctk.CTkFrame(master=self.master, bg_color="#000001", fg_color="#000001")  # Use CTkFrame
        pywinstyles.set_opacity(header_frame, color="#000001") # just add this line
        header_frame.pack(pady=10, padx=10)

        IMAGE_WIDTH = 1831/5
        IMAGE_HEIGHT = 417/5

        image = ctk.CTkImage(light_image=Image.open("images/ISO-Trainer.png"), dark_image=Image.open("images/ISO-Trainer.png"), size=(IMAGE_WIDTH , IMAGE_HEIGHT))
        
        # Create a label to display the image
        image_label = ctk.CTkLabel(header_frame, image=image, text='', corner_radius=42)
        image_label.grid(row=0, column=0, columnspan=3, pady=10, padx=10)  # Span across all columns
        

        # Create frame for the top section
        menu_dropdown_frame = ctk.CTkFrame(self.master, bg_color="#000001", fg_color="#000001", width=250)
        pywinstyles.set_opacity(menu_dropdown_frame, color="#000001")  # Set opacity
        menu_dropdown_frame.place(x=105, y=110)

        # Add a blank option at the beginning
        calibration_values_with_blank = [''] + self.calibration_data

        # Lists to hold the StringVars, dropdowns, and weight readings
        self.menu_dropdown_vars = []
        self.menu_dropdowns = []
        self.weight_readings_frames = []  # Frames for rounded corners
        self.weight_readings_labels = []  # Labels for weight readings

        # Create labels, dropdown menus, and weight reading boxes
        for i in range(2):  # For Channel 0 and Channel 1
            # Create labels for channels
            menu_dropdown_label = ctk.CTkLabel(menu_dropdown_frame, 
                                            text=f"Channel {i}", 
                                            width=100, 
                                            bg_color="#000001", 
                                            font=("Arial", 16, "bold"), 
                                            text_color="white")
            menu_dropdown_label.grid(row=0, column=i, padx=10, pady=5)

            # Create independent variables for each dropdown
            calibration_var = ctk.StringVar()
            self.menu_dropdown_vars.append(calibration_var)

            # Create dropdown menus
            dropdown = ctk.CTkComboBox(menu_dropdown_frame, 
                                    values=calibration_values_with_blank, 
                                    variable=calibration_var, 
                                    width=145, 
                                    justify="center",
                                    button_color="black",      # Button background color
                                    button_hover_color="gray", # Button hover color
                                    text_color="white",
                                    border_color="black")        # Text color inside the dropdown
            dropdown.grid(row=1, column=i, padx=10, pady=5)
            self.menu_dropdowns.append(dropdown)
                    # Set the initial displayed text to the dummy placeholder value
            dropdown.set("Select Load Cell")

            # Create frame for weight reading with rounded corners
            weight_reading_frame = ctk.CTkFrame(menu_dropdown_frame, 
                                                bg_color="#000001", 
                                                # fg_color="#333333",  # Box color
                                                corner_radius=15, 
                                                width=145, 
                                                height=50,
                                                border_color='black')  # Adjust height as needed
            weight_reading_frame.grid(row=2, column=i, padx=10, pady=10)
            self.weight_readings_frames.append(weight_reading_frame)
            pywinstyles.set_opacity(weight_reading_frame, value=0.85, color="#000001") # just add this line

            # Add weight reading label inside the frame
            weight_label = ctk.CTkLabel(weight_reading_frame, 
                                        text=f"Weight {i}\n0.0 Kg", 
                                        font=("Arial", 16, "bold"), 
                                        text_color="white",)
            weight_label.place(relx=0.5, rely=0.5, anchor="center")  # Center the label
            self.weight_readings_labels.append(weight_label)


        # Create frame for the top section
        participants_ID_frame = ctk.CTkFrame(self.master, bg_color="#000001", fg_color="#000001")  # Use CTkFrame
        pywinstyles.set_opacity(participants_ID_frame, color="#000001") # just add this line
        participants_ID_frame.place(x=110, y=250)

        self.participants_ID = ctk.CTkEntry(participants_ID_frame, width=310, placeholder_text="Participants ID (Output File Prefix)", border_color="black")
        self.participants_ID.grid(row=0, column=0, padx=5, pady=5)



        # Create frame RunTime
        runtime_frame = ctk.CTkFrame(self.master, bg_color="#000001", fg_color="#000001")  # Use CTkFrame
        pywinstyles.set_opacity(runtime_frame, color="#000001") # just add this line
        runtime_frame.place(x=110, y=288)

        self.runtime_entry = ctk.CTkEntry(runtime_frame, width=310-150, placeholder_text="RunTime (seconds)", border_color="black")
        self.runtime_entry.grid(row=0, column=0, padx=5, pady=5)


        # Create frame Weight Multiplier
        multiplier_frame = ctk.CTkFrame(self.master, bg_color="#000001", fg_color="#000001")  # Use CTkFrame
        pywinstyles.set_opacity(multiplier_frame, color="#000001") # just add this line
        multiplier_frame.place(x=110+165, y=288)


        # ✅ Create independent variable for multiplier dropdown
        self.multiplier_var = ctk.StringVar()
        self.menu_dropdown_vars.append(self.multiplier_var)

        # ✅ Create dropdown menu
        self.multiplier_dropdown = ctk.CTkComboBox(multiplier_frame, 
                                values=self.multiplier_values, 
                                variable=self.multiplier_var,
                                width=145, 
                                justify="center",
                                button_color="black",      # Button background color
                                button_hover_color="gray", # Button hover color
                                text_color="white",
                                border_color="black")      # Text color inside the dropdown
        self.multiplier_dropdown.grid(row=0, column=0, padx=5, pady=5)

        # ✅ Use `trace_add()` instead of `bind()`
        self.multiplier_var.trace_add("write", self.on_multiplier_change)

        # Set the initial displayed text to the dummy placeholder value
        self.multiplier_dropdown.set("Select Equipment")


        # Create frame for auto/manual mode
        mode_frame = ctk.CTkFrame(self.master, bg_color="#000001", fg_color="#000001")
        pywinstyles.set_opacity(mode_frame, color="#000001") # just add this line
        mode_frame.place(x=110, y=288+35)

        # Create radio buttons for auto/manual mode
        auto_start = ctk.StringVar(value="off")
        self.auto_trigger = ctk.CTkEntry(mode_frame, width=195, placeholder_text="Trigger Weight (Kg)", border_color='black')
        self.auto_trigger.grid(row=0, column=0, padx=5, pady=5)

        self.auto_start_switch = ctk.CTkSwitch(mode_frame, 
                                               text="Auto Start", 
                                               width=100, 
                                               bg_color="#000001", 
                                               fg_color="white", 
                                               font=("Arial", 12, "bold"), 
                                               text_color="white",
                                               variable=auto_start, 
                                               onvalue="on", 
                                               offvalue="off", 
                                               progress_color="#28a745")
        self.auto_start_switch.grid(row=0, column=1, padx=5, pady=5)


        # Create four buttons stacked vertically
        button_names = ["Connect", "Start Logging", "Stop Logging", "Reset", "Tare"]
        commands = [self.connect_phidget, self.start_logging, self.stop_logging, self.reset_display, self.tare_both_channels]
        button_colour = ["#28a745", "#007bff", "#dc3545", "#cc8400", "#A020F0"]
        start_button_position_x = 50
        start_button_position_y = 390

        button_positions_y = [start_button_position_y+0, start_button_position_y+37, start_button_position_y+74, start_button_position_y+111, start_button_position_y+148 ]
        self.buttons = []
        for name, command, colour, position_y in zip(button_names, commands, button_colour, button_positions_y):
            button = ctk.CTkButton(self.master, text=name, command=command, hover_color="grey", width=440, fg_color=colour, corner_radius=20, bg_color="#000001")
            button.pack(pady=5, padx = 20)  # Use pack with pady for vertical spacing
            self.buttons.append(button)
            self.buttons[-1].place(x=start_button_position_x, y= position_y)
            pywinstyles.set_opacity(button, color="#000001") # just add this line



        # Countdown Frame
        countdown_frame = ctk.CTkFrame(master=self.master, bg_color="#000001", corner_radius=20)  # Set a larger width
        pywinstyles.set_opacity(countdown_frame, value=0.85, color="#000001") # just add this line
        countdown_frame.place(x=270-75, y=590-5)
        # countdown label
        self.countdown_label = ctk.CTkLabel(countdown_frame, text="Timer\n0", width=100, font=("Arial", 42, "bold"), text_color="white", corner_radius=20)
        self.countdown_label.grid(row=0, column=0, pady=5, padx=5)




        # Create frame for the bottom section (terminal)
        terminal_frame = ctk.CTkFrame(master=self.master, bg_color="#000001", 
                                                # fg_color="#333333",  # Box color
                                                corner_radius=25, 
                                                width=145, 
                                                height=50,
                                                border_color='black')  # Use CTkFrame
        pywinstyles.set_opacity(terminal_frame, color="#000001") # just add this line
        terminal_frame.place(x=35, y=452+260)

        # Terminal (text output)
        self.terminal = ctk.CTkTextbox(terminal_frame, height=160, width=450, corner_radius=20)
        self.terminal.pack(pady=8, padx=8)



        # Create frame for the footer section with a larger width
        footer_frame = ctk.CTkFrame(master=self.master, width=200, bg_color="#000001", corner_radius=20)  # Set a larger width
        pywinstyles.set_opacity(footer_frame, value=0.85, color="#000001") # just add this line

        footer_frame.place(x=35, y=900)

        # Developer label
        developer_label = ctk.CTkLabel(footer_frame, text="Developed By: ", anchor="w", font=("Arial", 12, "bold"), text_color="white")
        developer_label.grid(row=0, column=0, sticky="w", padx=10, pady=5)  # Adjust padx as needed

        # Developer's name with hyperlink
        developer_name_label = ctk.CTkLabel(footer_frame, text="Brock Cooper", anchor="w", cursor="hand2", text_color="#007bff", font=("Arial", 12, "bold"))
        developer_name_label.grid(row=0, column=0, sticky="w", padx=95, pady=5)  # Adjust padx as needed
        developer_name_label.bind("<Button-1>", lambda event: self.open_website("https://brockcooper.au"))

        # space
        space_label = ctk.CTkLabel(footer_frame, text="", anchor="e")
        space_label.grid(row=0, column=2, sticky="e", padx=100, pady=5)  # Adjust padx as needed

        # Version label
        version_label = ctk.CTkLabel(footer_frame, text="Version 1.0", anchor="e", font=("Arial", 12, "bold"), text_color="white")
        version_label.grid(row=0, column=2, sticky="e", padx=10, pady=5)  # Adjust padx as needed

        # Handle window closing event
        self.master.protocol("WM_DELETE_WINDOW", self.on_close)
 

    def open_website(self, url):
            webbrowser.open_new(url)
            
    def change_theme(self, choice):
        ctk.set_appearance_mode(choice)


    def load_multiplier_options(self, file_path):
        """Reads the multiplier CSV file and returns a dictionary {Equipment: Multiplier}."""
        options = ["Select Equipment"]  # Default placeholder option
        multipliers = {}  # Dictionary to store {equipment: multiplier}

        try:
            with open(file_path, mode="r", newline="", encoding="utf-8") as file:
                reader = csv.reader(file)
                for row in reader:
                    if len(row) >= 2:  # Ensure at least two columns exist
                        raw_equipment = row[0].strip()  # First column: Equipment name
                        multiplier = float(row[1].strip())  # Second column: Multiplier value
                        
                        # Strip numbers & symbols from equipment name
                        equipment = re.sub(r"[\d\.\-]+$", "", raw_equipment).strip()

                        options.append(equipment)  # Store cleaned equipment name
                        multipliers[equipment] = multiplier  # Store corresponding multiplier value
                
                print("Loaded Multipliers:", multipliers)  # DEBUG PRINT

        except FileNotFoundError:
            print(f"Error: '{file_path}' not found.")
        except Exception as e:
            print(f"Error reading file: {e}")

        print(f"Current options: {options}")
        print(f"Current multipliers: {multipliers}")

        return options, multipliers


    def update_multiplier_value(self, selected_equipment):
        """Updates the multiplier value based on the selected equipment."""
        if selected_equipment in self.multipliers_dict:
            self.current_multiplier = self.multipliers_dict[selected_equipment]
            print(f"✅ Multiplier updated: {selected_equipment} -> {self.current_multiplier}")
        else:
            self.current_multiplier = 1.0  # Default multiplier if none is selected
            print("⚠️ Multiplier reset to default (1.0)")



    def on_multiplier_change(self, *args):
        """Event handler for dropdown selection changes."""
        self.selected_equipment = self.multiplier_var.get()
        
        # ✅ DEBUG PRINT to confirm event is triggered
        print(f"Dropdown changed! Selected: {self.selected_equipment}")

        # ✅ Ensure update_multiplier_value() gets called
        self.update_multiplier_value(self.selected_equipment)


    def tare_single_channel(self, voltageRatioInput, channel_id):
        """
        Tares a single channel using multiple samples.
        """
        num_samples = 16
        offset_sum = 0.0

        # Print which channel we're taring
        print(f"Starting tare process for Channel {channel_id}...")

        # Accumulate samples to compute average offset
        for _ in range(num_samples):
            offset_sum += voltageRatioInput.getVoltageRatio()
            time.sleep(voltageRatioInput.getDataInterval() / 1000.0)

        # Compute average offset
        average_offset = offset_sum / num_samples

        # Store offset in the correct variable
        if channel_id == 0:
            self.offset_channel_0 = average_offset
            self.calibrated_channel_0 = True
            print(f"Channel 0 Tare offset: {self.offset_channel_0}")
            self.update_terminal(f"Channel 0 Tare offset: {self.offset_channel_0}\n")
        elif channel_id == 1:
            self.offset_channel_1 = average_offset
            self.calibrated_channel_1 = True
            print(f"Channel 1 Tare offset: {self.offset_channel_1}")
            self.update_terminal(f"Channel 1 Tare offset: {self.offset_channel_1}\n")


    def tare_both_channels(self):
        
        if self.connected_flag == False:
            self.update_terminal("🔗Please Connect to the PhidgetBridge device\n")
            return
        
        self.update_terminal(f"Taring...\n")
        self.terminal.update_idletasks()  # Force update so user sees "Taring..." immediately

        if getattr(self, 'voltageRatioInput0', None) is not None:
            self.tare_single_channel(self.voltageRatioInput0, 0)
        if getattr(self, 'voltageRatioInput1', None) is not None:
            self.tare_single_channel(self.voltageRatioInput1, 1)
        print("Tare complete for all connected channels.")
        self.update_terminal("Tare complete for all connected channels.\n")
        # final update if needed
        self.terminal.update_idletasks()


    def onVoltageRatioChange(self, ch, voltageRatio):
        channel_id = ch.getChannel()

        if channel_id == 0:
            # If we never loaded a valid gain for channel 0, skip
            if self.gain_channel_0 is None:
                return
            # Check calibration flag as well
            if not self.calibrated_channel_0:
                return

            offset = self.offset_channel_0
            gain = self.gain_channel_0
            label_index = 0

        elif channel_id == 1:
            # If we never loaded a valid gain for channel 1, skip
            if self.gain_channel_1 is None:
                return
            # Check calibration flag as well
            if not self.calibrated_channel_1:
                return

            offset = self.offset_channel_1
            gain = self.gain_channel_1
            label_index = 1

        else:
            # Not a channel we care about
            return

        # Calculate weights
        weight_newtons = (voltageRatio - offset) * float(gain)
        weight_grams = weight_newtons * 1000 * float(self.current_multiplier)
        weight_kg = weight_grams / 1000.0
        timestamp = time.strftime("%Y-%m-%d %H:%M:%S")

        # Print the weight for debugging
        if weight_kg < 0.05 and weight_grams > -99.99 * float(self.current_multiplier):
            display_kg = 0.00
        elif weight_kg < -100.00 * float(self.current_multiplier):
            display_kg = weight_kg
        else:
            display_kg = weight_kg
      

        # print(f"{timestamp} - Channel {channel_id}: {weight_grams:.2f} g, {display_kg:.2f} kg")

        # Update the correct UI label
        self.weight_readings_labels[label_index].configure(text=f"Weight {channel_id}\n{display_kg:.1f} Kg")

        return weight_grams






    def connect_phidget(self):
        # Clear terminal
        self.clear_terminal()
        self.update_terminal(f"Connecting...\n")
        self.terminal.update_idletasks()  # Force update so user sees "Connecting..." immediately

        # 🔹 **1) Close existing connections if they exist**
        if getattr(self, 'voltageRatioInput0', None) is not None:
            try:
                self.voltageRatioInput0.setOnVoltageRatioChangeHandler(None)
                self.voltageRatioInput0.close()
            except Exception as e:
                print(f"Error closing Channel 0: {e}")
            self.voltageRatioInput0 = None

        if getattr(self, 'voltageRatioInput1', None) is not None:
            try:
                self.voltageRatioInput1.setOnVoltageRatioChangeHandler(None)
                self.voltageRatioInput1.close()
            except Exception as e:
                print(f"Error closing Channel 1: {e}")
            self.voltageRatioInput1 = None

        # 🔹 **2) Read calibration files (if any selected)**
        current_directory = os.path.dirname(os.path.abspath("ISO-Trainer.py"))
        file_path_channel_0 = os.path.join(current_directory, "calibration-data", f"{self.menu_dropdowns[0].get()}.csv")
        file_path_channel_1 = os.path.join(current_directory, "calibration-data", f"{self.menu_dropdowns[1].get()}.csv")

        self.gain_channel_0 = self.read_csv(file_path_channel_0)
        self.gain_channel_1 = self.read_csv(file_path_channel_1)

        # 🔹 **3) Early exit if NO calibration files are selected for BOTH channels**
        if self.gain_channel_0 is None and self.gain_channel_1 is None:
            self.update_terminal("❌ ERROR: No valid calibration data selected for either channel. Please choose a valid load cell.\n")
            print("❌ ERROR: No valid calibration data selected. Connection aborted.")
            self.menu_dropdowns[0].configure(border_color="red", button_color="red")
            self.menu_dropdowns[1].configure(border_color="red", button_color="red")
            return  # **Break out of function early**



        # 🔹 **4) Reattach channels only if valid calibration data exists**
        def voltage_ratio_callback(ch, voltageRatio):
            self.onVoltageRatioChange(ch, voltageRatio)

        # **Channel 0**
        if self.gain_channel_0 is not None:
            try:
                self.voltageRatioInput0 = VoltageRatioInput()
                self.voltageRatioInput0.setChannel(0)
                self.voltageRatioInput0.setOnVoltageRatioChangeHandler(voltage_ratio_callback)
                self.update_terminal("Checking connection for Channel 0...\n")
                self.terminal.update_idletasks()
                self.voltageRatioInput0.openWaitForAttachment(1500)
                self.voltageRatioInput0.setDataInterval(50)
                self.update_terminal("✅ Channel 0 connected successfully.\n")
                self.menu_dropdowns[0].configure(border_color="green", button_color="green")
                print("Channel 0 connected.")
            except PhidgetException as e:
                self.update_terminal(f"❌ Failed to connect Channel 0: {e}\n")
                print(f"Failed to attach Channel 0: {e}")
                self.menu_dropdowns[0].configure(border_color="black", button_color="black")
                self.voltageRatioInput0 = None
        else:
            self.update_terminal("⚠️ No valid calibration data for Channel 0. Skipping connection.\n")
            print("No valid calibration data for Channel 0. Skipping connection.")
            self.menu_dropdowns[0].configure(border_color="black", button_color="black")


        # **Channel 1**
        if self.gain_channel_1 is not None:
            try:
                self.voltageRatioInput1 = VoltageRatioInput()
                self.voltageRatioInput1.setChannel(1)
                self.voltageRatioInput1.setOnVoltageRatioChangeHandler(voltage_ratio_callback)
                self.update_terminal("Checking connection for Channel 1...\n")
                self.terminal.update_idletasks()
                self.voltageRatioInput1.openWaitForAttachment(1500)
                self.voltageRatioInput1.setDataInterval(50)
                self.update_terminal("✅ Channel 1 connected successfully.\n")
                self.menu_dropdowns[1].configure(border_color="green", button_color="green")
                print("Channel 1 connected.")
            except PhidgetException as e:
                self.update_terminal(f"❌ Failed to connect Channel 1: {e}\n")
                print(f"Failed to attach Channel 1: {e}")
                self.menu_dropdowns[1].configure(border_color="black", button_color="black")
                self.voltageRatioInput1 = None
        else:
            self.update_terminal("⚠️ No valid calibration data for Channel 1. Skipping connection.\n")
            print("No valid calibration data for Channel 1. Skipping connection.")
            self.menu_dropdowns[1].configure(border_color="black", button_color="black")



    

        # 🔹 **5) Ensure multiplier is selected**
        multiplier_value = self.multiplier_dropdown.get()
        if not multiplier_value or multiplier_value == "Select Equipment":
            self.update_terminal("❌ ERROR: Please select equipment before connecting.\n")
            self.multiplier_dropdown.configure(border_color="red", button_color="red")
            self.terminal.update_idletasks()
            return  # **Stop the connection process**
        
        # ✅ **Update the multiplier before proceeding**
        self.update_multiplier_value(multiplier_value)

        # Reset dropdown colors to normal
        self.multiplier_dropdown.configure(border_color="green", button_color="green")



        # 🔹 **6) Tare channels only if connected**
        if self.voltageRatioInput0 is not None:
            self.update_terminal("Taring channel 0...\n")
            self.tare_single_channel(self.voltageRatioInput0, 0)
            self.menu_dropdowns[0].configure(border_color="green", button_color="green")
        else:
            self.menu_dropdowns[0].configure(border_color="black", button_color="black")


        if self.voltageRatioInput1 is not None:
            self.update_terminal("Taring channel 1...\n")
            self.tare_single_channel(self.voltageRatioInput1, 1)
            self.menu_dropdowns[1].configure(border_color="green", button_color="green")
        else:
            self.menu_dropdowns[1].configure(border_color="black", button_color="black")

        # 🔹 **7) Final Confirmation**
        self.convert_fields()
        self.update_terminal(f"Equipment Multiplier: {self.multiplier_dropdown.get()} -> {self.current_multiplier}\n")
        self.update_terminal("✅ Connection process complete.\n")
        self.connected_flag = True
        print("Connection process complete.")



    def convert_fields(self):
        try:
            run_time = int(self.runtime_entry.get()) if self.runtime_entry.get() else 0

        except ValueError:
            self.update_terminal("Error: Please enter valid numerical values\n")
            raise ValueError("Please enter valid numerical values")
            
        if run_time == 0:
            self.countdown_label.configure(text=f"Timer\n♾️")
        elif run_time != 0:
            self.countdown_label.configure(text=f"Timer\n{run_time}")
        else:
            self.countdown_label.configure(text=f"Timer\n♾️")

        # self.runtime_entry.configure(state="disabled")
        # self.auto_start_switch.configure(state="disabled")
        # self.participants_ID.configure(state="disabled")
        self.menu_dropdowns[0].configure(state="disabled")
        self.menu_dropdowns[1].configure(state="disabled")
        self.multiplier_dropdown.configure(state="disabled")


    def start_logging(self):

        if self.connected_flag == False:
            self.update_terminal("🔗Please Connect to the PhidgetBridge device\n")
            return
        
        self.runtime_entry.configure(state="disabled")
        self.auto_trigger.configure(state="disabled")
        self.auto_start_switch.configure(state="disabled")
        self.participants_ID.configure(state="disabled")
        
        """Starts the logging process either manually or automatically when weight exceeds the threshold."""
        if self.logging_active:
            self.update_terminal("Logging already in progress...\n")
            return

        # Get user input values
        participant_id = self.participants_ID.get().strip()
        record_time = self.runtime_entry.get().strip()
        trigger_weight = self.auto_trigger.get().strip()

        # Set default file save location
        folder_path = os.path.join(os.getcwd(), "ISOTrainer-Logs")
        os.makedirs(folder_path, exist_ok=True)  # Ensure folder exists

        # Format the filename
        current_datetime = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        file_name = os.path.join(folder_path, f"{participant_id} - {self.selected_equipment} - ISOTrainer_Data_{current_datetime}.csv")

        # Check if we are in auto mode
        auto_start = self.auto_start_switch.get() == "on"
        trigger_weight = float(trigger_weight) if trigger_weight else None

        # Start countdown if runtime is given
        if record_time.isdigit():
            total_time = int(record_time)
            self.countdown_label.configure(text=f"Timer\n{total_time}")
        else:
            total_time = None  # Infinite logging
            self.countdown_label.configure(text="Timer\n♾️")

        self.logging_active = False  # Initially set to False (to wait for weight threshold)
        self.live_update_flag = True

        # If manual logging, start immediately; otherwise, wait for threshold
        if auto_start:
            self.update_terminal(f"Waiting to start logging... File: {file_name}\n")
        else:
            self.update_terminal(f"Manual logging started... File: {file_name}\n")
            self.logging_active = True  # Start logging immediately

        # Create & Write Header
        with open(file_name, mode="w", newline="") as file:
            writer = csv.writer(file)
            writer.writerow(["Timestamp (Seconds)", "Channel 0 Weight (Kg)", "Channel 1 Weight (Kg)", "Combined Weight (Kg)"])  # Header

        # Function to log data every 0.2s
        def log_loop():
            timestamp = 0
            start_time = time.time()  # Set logging start time
            weight_below_threshold_counter = 0  # Counter to confirm logging stop condition

            while self.live_update_flag:
                weight_0 = self.get_current_weight(0)
                weight_1 = self.get_current_weight(1)

                # **Auto-Start Logic** (Only start when weight crosses threshold)
                if auto_start and trigger_weight is not None and not self.logging_active:
                    if weight_0 >= trigger_weight or weight_1 >= trigger_weight:
                        self.logging_active = True
                        self.update_terminal("Auto logging started.\n")
                        self.auto_trigger.configure(border_color="green")

                        start_time = time.time()  # Set start time
                    else:
                        time.sleep(0.2)  # Wait and check again
                        continue  # Skip logging if the threshold isn't met yet

                # **Auto-Stop Logic** (Only stop logging if no record time is given)
                if auto_start and trigger_weight is not None and self.logging_active:
                    if weight_0 < trigger_weight and weight_1 < trigger_weight:
                        weight_below_threshold_counter += 1
                    else:
                        weight_below_threshold_counter = 0  # Reset counter if weight rises again

                    # If weight is below threshold for 3 consecutive readings (0.6s), stop logging
                    if weight_below_threshold_counter >= 3 and total_time is None:
                        self.logging_active = False
                        self.update_terminal("Auto logging stopped (weight dropped below threshold for 0.6s).\n")
                        break  # Exit loop

                if self.logging_active:
                    elapsed_time = time.time() - start_time

                    # Capture weights
                    # timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    timestamp = timestamp + 0.2

                    # Write to CSV
                    with open(file_name, mode="a", newline="") as file:
                        writer = csv.writer(file)
                        writer.writerow([timestamp, weight_0, weight_1, weight_0 + weight_1])

                    # Update UI countdown
                    if total_time is not None:  # If countdown is active
                        remaining_time = total_time - int(elapsed_time)
                        if remaining_time <= 0:
                            self.countdown_label.configure(text="Timer\n0")
                            self.logging_active = False  # Stop logging when countdown hits zero
                            self.update_terminal("💾 Logging complete.\n")        
                            self.runtime_entry.configure(state="normal")
                            self.auto_trigger.configure(state="normal")
                            self.auto_start_switch.configure(state="normal")
                            self.participants_ID.configure(state="normal")
                            
                            break
                        else:
                            self.countdown_label.configure(text=f"Timer\n{remaining_time}")
                    else:
                        self.countdown_label.configure(text=f"Timer\n{int(elapsed_time)}")  # Count Up

                time.sleep(0.2)  # Log every 0.2 seconds

            self.logging_active = False  # Ensure flag is reset
            self.auto_trigger.configure(border_color="black")
            self.update_terminal("💾 Logging Stopped.\n")
            self.runtime_entry.configure(state="normal")
            self.auto_trigger.configure(state="normal")
            self.auto_start_switch.configure(state="normal")
            self.participants_ID.configure(state="normal")
                            

        # Start logging in a separate thread
        logging_thread = threading.Thread(target=log_loop, daemon=True)
        logging_thread.start()


    def stop_logging(self):
        """Stops the logging process."""
        self.runtime_entry.configure(state="normal")
        self.auto_start_switch.configure(state="normal")
        self.participants_ID.configure(state="normal")
        self.auto_trigger.configure(state="normal")

        if self.logging_active:
            self.logging_active = False
            self.live_update_flag = False
            self.update_terminal("Logging manually stopped.\n")
        else:
            self.update_terminal("No active logging session.\n")


    def get_current_weight(self, channel_id):
        """Returns the current weight for a specific channel."""
        try:
            label_text = self.weight_readings_labels[channel_id].cget("text")
            return float(label_text.split("\n")[1].split(" ")[0])  # Extract number from "Weight X\nY.Z Kg"
        except Exception:
            return 0.0  # Default if error


    def get_total_runtime(self):
        runtime = self.runtime_entry.get()
        if not runtime:
            return float('inf')
        else:
            return int(runtime)


    def reset_display(self):

       # Clear terminal
        self.clear_terminal()
        # 1) Close existing connections if they exist
        #    (This stops any ongoing reading/stream)

        if getattr(self, 'voltageRatioInput0', None) is not None:
            try:
                # Remove any callback references just to be safe
                self.voltageRatioInput0.setOnVoltageRatioChangeHandler(None)
                self.voltageRatioInput0.close()  # Close connectionself.menu_dropdowns[0]
            except Exception as e:
                print(f"Error closing Channel 0: {e}")
            self.voltageRatioInput0 = None  # Clear reference

        if getattr(self, 'voltageRatioInput1', None) is not None:
            try:
                self.voltageRatioInput1.setOnVoltageRatioChangeHandler(None)
                self.voltageRatioInput1.close()
            except Exception as e:
                print(f"Error closing Channel 1: {e}")
            self.voltageRatioInput1 = None

    
        self.menu_dropdowns[0].configure(state= "normal")
        self.menu_dropdowns[1].configure(state= "normal")
        self.multiplier_dropdown.configure(state= "normal")

        self.menu_dropdowns[0].set("Select Load Cell")
        self.menu_dropdowns[1].set("Select Load Cell")
        self.multiplier_dropdown.set("Select Equipment")

        self.menu_dropdowns[0].configure(border_color="black", button_color="black")
        self.menu_dropdowns[1].configure(border_color="black", button_color="black")
        self.multiplier_dropdown.configure(border_color="black", button_color="black")

        self.weight_readings_labels[0].configure(text=f"Weight 0\n0.0 Kg")
        self.weight_readings_labels[1].configure(text=f"Weight 1\n0.0 Kg")


        self.live_update_flag = False  # Reset live update flag
        self.record_time_flag = False

        self.connected_flag = False

        
        # Stop logging
        self.stop_logging()

        
        # Clear terminal
        self.clear_terminal()

        self.live_update_flag = True  # Reset live update flag


        self.runtime_entry.delete(0,100)
        self.auto_trigger.delete(0,100)
        self.participants_ID.delete(0,100)



        self.runtime_entry.configure(placeholder_text="RunTime (seconds)")
        self.auto_trigger.configure(placeholder_text="Trigger Weight (Kg)")
        self.participants_ID.configure(placeholder_text="Participants ID (Output File Prefix)")
        self.countdown_label.configure(text=f"Timer\n0")

    
        self.runtime_entry.configure(state="normal")
        self.auto_start_switch.configure(state="normal")
        self.participants_ID.configure(state="normal")
        self.auto_trigger.configure(state="normal")


    def clear_terminal(self):
        self.terminal.delete(1.0, ctk.END)
        self.terminal.update()


    def update_terminal(self, message):
        self.terminal.insert(ctk.END, message)
        self.terminal.see(ctk.END)  # Scroll to the end of the text

    def on_close(self):
        msg = CTkMessagebox(title="Exit?", message="Do you want to close the program?",
                        icon="question", option_1="No", option_2="Yes")
        response = msg.get()
        
        if response=="Yes":
            self.live_update_flag = False
            
            self.reset_display()
            self.master.destroy()  


    def read_csv(self, file_path):
        try:
            # Open the CSV file in read mode
            with open(file_path, mode='r', newline='', encoding='utf-8') as file:
                # Create a CSV reader object
                csv_reader = csv.reader(file)
                
                # Loop through the rows in the CSV file
                for row in csv_reader:
                    if row:  # Ensure the row is not empty
                        key, value = row[0], row[1]
                        
                        if key.lower() == "gain":  # Check if the key is "gain"
                            try:
                                gain_value = float(value)  # Convert the value to a float
                                return gain_value  # Return the extracted gain value
                            except ValueError:
                                print(f"Error: Invalid value for gain in {file_path}.")
                                return None
            print(f"Error: 'gain' not found in {file_path}.")
            return None
        
        except FileNotFoundError:
            print(f"Error: The file '{file_path}' was not found.")
            return None
        except Exception as e:
            print(f"Error: {e}")
            return None




import os
import webbrowser
import customtkinter as ctk

def create_about_dialog(root):
    cur_dir = os.getcwd()
    cur_dir = cur_dir.replace("\\", "/")
    icon_path = "images/icon.ico"

    # Set the icon for the about dialog
    about_dialog = ctk.CTkToplevel(root)  # Use CTkToplevel to make it a separate window
    about_dialog.geometry("560x650")  # Fixed window size (smaller height)
    about_dialog.title("About")
    about_dialog.attributes("-topmost", True)  # Keep the window on top
    about_dialog.iconbitmap(icon_path)  # Set window icon

    # Scrollable frame for content
    scrollable_frame = ctk.CTkScrollableFrame(master=about_dialog, width=540, height=550)
    scrollable_frame.pack(padx=10, pady=0, fill="both", expand=True)

    # Application name label
    app_name_label = ctk.CTkLabel(master=scrollable_frame,
                                  text="ISO Trainer Interface",
                                  font=("Arial", 18, "bold"))
    app_name_label.pack(pady=10)

    # Version label
    version_label = ctk.CTkLabel(master=scrollable_frame,
                                 text="Version: 1.0",
                                 font=("Arial", 12, "bold"))
    version_label.pack()

    # Author label
    author_label = ctk.CTkLabel(master=scrollable_frame,
                                text="Developed by: Brock Cooper",
                                font=("Arial", 12, "bold"))
    author_label.pack()

    # Description
    description_label = ctk.CTkLabel(master=scrollable_frame,
                                     text="This program is designed for the PhidgetBridge 1046_0.\n"
                                          "Calibration data (gain) should be stored in the calibration-data folder.\n"
                                          "You can select these from the dropdown menus for each channel.\n"
                                          "You may use either Channel 0 or Channel 1 independently.\n\n",
                                     font=("Arial", 12),
                                     wraplength=500)
    description_label.pack()

    # Description
    list_label = ctk.CTkLabel(master=scrollable_frame,
                                     text="The program includes multiple input fields:\n"
                                          "• Load Cell Channel Selection (0 & 1)\n"
                                          "• Participants ID\n"
                                          "• Runtime (seconds)\n"
                                          "• Select Equipment\n"
                                          "• Trigger Weight (Kg)\n"
                                          "• Auto Start Switch\n\n"
                                          "📌 **Before using the program, install the Phidget driver below:**",
                                     font=("Arial", 12),
                                     wraplength=500,
                                     justify="left")
    list_label.pack()


    # Clickable links
    def open_phidgets_driver_32():
        webbrowser.open_new("https://www.phidgets.com/downloads/phidget22/libraries/windows/Phidget22-x86.exe")

    def open_phidgets_driver_64():
        webbrowser.open_new("https://www.phidgets.com/downloads/phidget22/libraries/windows/Phidget22-x64.exe")

    hyperlink_label_32 = ctk.CTkLabel(master=scrollable_frame,
                                      text="⬇ 32-bit Phidget22 Driver Download",
                                      font=("Arial", 12, "bold"),
                                      text_color="#4286f4",
                                      cursor="hand2")
    hyperlink_label_32.pack()
    hyperlink_label_32.bind("<Button-1>", lambda e: open_phidgets_driver_32())

    hyperlink_label_64 = ctk.CTkLabel(master=scrollable_frame,
                                      text="⬇ 64-bit Phidget22 Driver Download",
                                      font=("Arial", 12, "bold"),
                                      text_color="#4286f4",
                                      cursor="hand2")
    hyperlink_label_64.pack()
    hyperlink_label_64.bind("<Button-1>", lambda e: open_phidgets_driver_64())

    # Logging Features Breakdown
    extra_info_label = ctk.CTkLabel(master=scrollable_frame,
                                    text="📝 **Manual Mode (Auto-Start OFF):**\n"
                                         "• Logging starts **immediately** when 'Start Logging' is pressed.\n"
                                         "• Stops when:\n"
                                         "  - The user presses **'Stop Logging'**.\n"
                                         "  - The **countdown timer** (if set) reaches `0`.\n"
                                         "  - Otherwise, logging continues indefinitely.\n\n"
                                         "🤖 **Automatic Mode (Auto-Start ON):**\n"
                                         "• Logging **automatically starts** when weight **exceeds** the trigger threshold.\n"
                                         "• Stops when:\n"
                                         "  - The weight **drops below the trigger** for **0.6 seconds (3 readings)**.\n"
                                         "  - The **countdown timer** (if set) reaches `0`.\n"
                                         "  - Otherwise, logs continuously.\n\n"
                                         "⏳ **Countdown Timer Behavior:**\n"
                                         "• If a **record time** is set, the timer **counts down** to `0`.\n"
                                         "• If **no time** is set, the timer **counts up indefinitely (♾️)**.\n\n"
                                         "🔄 **Auto-Start vs. Auto-Stop:**\n"
                                         "• **Manual Start (Auto-Start OFF):** Logging starts immediately.\n"
                                         "• **Manual Stop (Auto-Start OFF):** Stops manually or when timer reaches `0`.\n"
                                         "• **Auto Start (Auto-Start ON):** Starts only when weight crosses the set trigger.\n"
                                         "• **Auto Stop (Auto-Start ON):** Stops if weight stays below trigger for **0.6s**.\n\n"
                                         "This ensures a **flexible, automatic, and user-friendly logging system!** 🎯",
                                    font=("Arial", 12),
                                    wraplength=500,
                                    justify="left",
                                    padx=20)
    extra_info_label.pack()

    # Copyright Label
    copyright_label = ctk.CTkLabel(master=scrollable_frame,
                                   text="Copyright © 2024 Brock Cooper",
                                   font=("Arial", 10))
    copyright_label.pack()

    # Close Button
    close_button = ctk.CTkButton(master=about_dialog,
                                 text="Close",
                                 command=about_dialog.destroy)
    
    close_button.pack(pady=10)

    about_dialog.mainloop()


def main():
    root = ctk.CTk()
    root.geometry("540x960")  # Set the initial size of the window to 1000x800 pixels
    # root.geometry("540x960+2500+180")  # Set the initial size of the window to 1000x800 pixels

    root.resizable(False, False)


    app = MyInterface(root)
    # Handle window closing event
    root.protocol("WM_DELETE_WINDOW", app.on_close)

    # Set the window icon
    cur_dir = os.getcwd()
    cur_dir = cur_dir.replace("\\", "/")
    # icon_path = cur_dir+"/favicon.ico"
    icon_path = "images/icon.ico"
    ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(icon_path)
    print(icon_path)
    root.iconbitmap(icon_path)  # Set the window icon
    

    # Create a Tkinter menubar
    menubar = tk.Menu(root)

    # Create "File" menu
    file_menu = tk.Menu(menubar, tearoff=0)
    menubar.add_cascade(label="File", menu=file_menu)


    # Add "Help" command directly to "File" menu
    file_menu.add_command(label="Help", command=lambda: create_about_dialog(root))

    root.configure(menu=menubar)
    root.mainloop()

if __name__ == "__main__":
    main()