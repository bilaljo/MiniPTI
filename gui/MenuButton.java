import java.awt.event.ActionEvent;
import java.awt.event.ActionListener;
import java.io.File;
import javax.swing.JFileChooser;

public class MenuButton implements ActionListener {
    final JFileChooser fc = new JFileChooser();
    public void actionPerformed(ActionEvent e) {
        if (e.getSource() == openButton) {
            int returnVal = fc.showOpenDialog(FileManager.this);
            if (returnVal == JFileChooser.APPROVE_OPTION) {
                File file = fc.getSelectedFile();
            } else {
                log.append("Open command cancelled by user." + newline);
            }
        }
    }
}
