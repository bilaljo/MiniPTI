import javax.swing.*;
import java.awt.*;

public class Main {
    public static void main(String[] args) {
        GUI MainWindow = new GUI();

        MainWindow.createMenuItem("Phase Scan");
        MainWindow.createMenuItem("Lock in Amplifier");
        MainWindow.createMenuItem("Measurement");

        Menu lockInAmplifier = new Menu();
        lockInAmplifier.addMenuItem("Open", GUI.menus.get("Lock in Amplifier"));
        lockInAmplifier.addMenuItem("Run", GUI.menus.get("Lock in Amplifier"));
        Menu phaseScan = new Menu();
        phaseScan.addMenuItem("Open", GUI.menus.get("Phase Scan"));
        phaseScan.addMenuItem("Run", GUI.menus.get("Phase Scan"));

        Menu measurement = new Menu();
        measurement.addMenuItem("Open", GUI.menus.get("Measurement"));
        measurement.addMenuItem("Run", GUI.menus.get("Measurement"));

        MainWindow.show();
    }
}
