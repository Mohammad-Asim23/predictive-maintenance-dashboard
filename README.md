# Predictive Maintenance Dashboard

This project provides a predictive maintenance dashboard using IoT and AI. The dashboard displays real-time sensor data and allows users to customize how they view the data. It also includes a demo mode that reads sensor data from an Excel file.

## Features

- Real-time sensor data monitoring using MQTT.
- Customizable graphs (gauge, line, bar) with adjustable min/max values and colors.
- Demo mode that reads data from an Excel file.
- Supports predictive maintenance for industrial equipment.

## Installation

### Prerequisites

Make sure you have the following installed:

1. **Python 3.x**: You can download it from [here](https://www.python.org/downloads/).
2. **Git** (optional, for cloning the repository): Download it from [here](https://git-scm.com/).

### Clone the Repository

To download the project, run the following command in your terminal or command prompt:

```bash
git clone https://github.com/Mohammad-Asim23/predictive-maintenance-dashboard.git
```
## Navigate to the Project Directory:

```bash
cd predictive-maintenance-dashboard
```

### Install Dependencies Manually

```bash
pip install dash paho-mqtt pandas plotly
```
## Configuartion
The project requires a config.json and water_plant_sensor_data.csv file to run. This file should be in the root of the project.

### Running the Project
Once you’ve installed the dependencies and set up the configuration, you can run the project using:

```bash
python python-dweet.py
```
