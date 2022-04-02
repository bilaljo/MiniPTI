import javax.swing.*;
import java.util.HashMap;
import java.util.Map;
import java.awt.*;

public class GUI {
    public static JMenuBar menuBar = new JMenuBar();
    public static JFrame frame = new JFrame();
    public static Map<String, JMenu> menus = new HashMap<String, JMenu>();
    public GUI() {
        menuBar = new JMenuBar();
        frame = new JFrame("Passepartout");
    }
    public void createMenuItem(String menuItem) {
        menus.put(menuItem, new JMenu(menuItem));
        menuBar.add(menus.get(menuItem));
    }
    public void show() {
        frame.setDefaultCloseOperation(JFrame.EXIT_ON_CLOSE);
        frame.setSize(300,300);
        frame.getContentPane().add(BorderLayout.NORTH, menuBar);
        frame.setVisible(true);
    }
}
