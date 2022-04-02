import javax.swing.*;
import java.util.Map;
import java.util.HashMap;
import java.awt.event.*;

public class Menu{
    private Map<String, JMenu> menuItems = new HashMap<String, JMenu>();
    public void addMenuItem(String menuName, JMenu menuBar) {
        menuItems.put(menuName, new JMenu(menuName));
        menuBar.add(menuItems.get(menuName));
    }
}
