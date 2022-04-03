#include <wx/wxprec.h>
#include <wx/string.h>
#include <wx/menu.h>
#include <wx/textctrl.h>

#ifndef WX_PRECOMP
    #include <wx/wx.h>
#endif
 
class MyApp : public wxApp
{
public:
    virtual bool OnInit();
};
 
class MyFrame : public wxFrame
{
public:
    MyFrame();
 
private:
    void OpenLockIn(wxCommandEvent& event);
    void OpenPhaseScan(wxCommandEvent& event);
    void OpenMeasurement(wxCommandEvent& event);
    void OnExit(wxCommandEvent& event);
    void OnAbout(wxCommandEvent& event);
    void RunLockIn(wxCommandEvent& event);
};
 
enum
{
    ID_LockInOpen,
    ID_LockInRun,
    ID_PhaseScanOpen,
    ID_PhaseScanRun,
    ID_MeasurementOpen,
    ID_MeasurementRun,
};
 
wxIMPLEMENT_APP(MyApp);
 
bool MyApp::OnInit() {
    MyFrame *frame = new MyFrame();
    frame->Show(true);
    return true;
}
 
MyFrame::MyFrame() : wxFrame(NULL, wxID_ANY, "Passepartout") {
    wxMenu *LockInAmplifier = new wxMenu;
    LockInAmplifier->Append(ID_LockInOpen, "Open...\tCtrl-O",
                     "Opens data for Lock in Amplifier");
    LockInAmplifier->Append(ID_LockInRun, "Run\tCtrl-L",
                     "Exectuing a Lock in Amplifier for a given data set.");                
    LockInAmplifier->AppendSeparator();
    LockInAmplifier->Append(wxID_EXIT);

    wxMenu *PhaseScan = new wxMenu;
    PhaseScan->Append(ID_PhaseScanOpen, "Open...\tCtrl-O",
                     "Opens data for Phase Scan");
    PhaseScan->Append(ID_PhaseScanRun, "Run\tCtrl-L",
                     "Help string shown in status bar for this menu item");
    PhaseScan->AppendSeparator();
    PhaseScan->Append(wxID_EXIT);

    wxMenu *Measurement = new wxMenu;
    Measurement->Append(ID_MeasurementOpen, "Open...\tCtrl-O",
                     "Opens data for PTI Inversion");
    Measurement->Append(ID_MeasurementRun, "Run\tCtrl-L",
                     "Help string shown in status bar for this menu item");
    Measurement->AppendSeparator();
    Measurement->Append(wxID_EXIT);

    wxMenu *menuHelp = new wxMenu;
    menuHelp->Append(wxID_ABOUT);
 
    wxMenuBar *menuBar = new wxMenuBar;
    menuBar->Append(PhaseScan, "&Phase Scan");
    menuBar->Append(LockInAmplifier, "&Lock In Amplifier");
    menuBar->Append(Measurement, "&PTI Inversion");
    menuBar->Append(menuHelp, "&Help");
 
    SetMenuBar(menuBar);
 
    Bind(wxEVT_MENU, &MyFrame::OpenLockIn, this, ID_LockInOpen);
    Bind(wxEVT_MENU, &MyFrame::RunLockIn, this, ID_LockInRun);
    Bind(wxEVT_MENU, &MyFrame::OpenPhaseScan, this, ID_PhaseScanOpen);
    Bind(wxEVT_MENU, &MyFrame::OnAbout, this, wxID_ABOUT);
    Bind(wxEVT_MENU, &MyFrame::OnExit, this, wxID_EXIT);
}

void MyFrame::OnExit(wxCommandEvent& event)
{
    Close(true);
}
 
void MyFrame::OnAbout(wxCommandEvent& event)
{
    wxMessageBox("This is the measurement software for a PTI provided by FHNW.\nhttps://www.fhnw.ch/en/\nAuthor of the Softwar: Jonas Bilal",
                 "About Passepartout Software", wxOK | wxICON_INFORMATION);
}
 
void MyFrame::OpenLockIn(wxCommandEvent& event) {
    	wxFileDialog* OpenDialog = new wxFileDialog(
		this, _("Choose a file to open"), wxEmptyString, wxEmptyString, 
		_("Text files (*.txt)|*.txt|Comma Separated Values (*.csv)|*.csv|Binary files (*.bin)|*.bin|"),
		wxFD_OPEN, wxDefaultPosition);

	// Creates a "open file" dialog with 4 file types
	if (OpenDialog->ShowModal() == wxID_OK) // if the user click "Open" instead of "Cancel"
	{
		//CurrentDocPath = OpenDialog->GetPath();
		// Sets our current document to the file the user selected
		//MainEditBox->LoadFile(CurrentDocPath); //Opens that file
		//SetTitle(wxString("Edit - ") << 
		//	OpenDialog->GetFilename()); // Set the Title to reflect the file open
	}
	OpenDialog->Destroy();

}

void MyFrame::OpenPhaseScan(wxCommandEvent& event) {
    	wxFileDialog* OpenDialog = new wxFileDialog(
		this, _("Choose a file to open"), wxEmptyString, wxEmptyString, 
		_("Text files (*.txt)|*.txt|Comma Separated Values (*.csv)|*.csv|Binary files (*.bin)|*.bin|"),
		wxFD_OPEN, wxDefaultPosition);

	// Creates a "open file" dialog with 4 file types
	if (OpenDialog->ShowModal() == wxID_OK) // if the user click "Open" instead of "Cancel"
	{
		//CurrentDocPath = OpenDialog->GetPath();
		// Sets our current document to the file the user selected
		//MainEditBox->LoadFile(CurrentDocPath); //Opens that file
		//SetTitle(wxString("Edit - ") << 
		//	OpenDialog->GetFilename()); // Set the Title to reflect the file open
	}
    	OpenDialog->Destroy();
}

void MyFrame::RunLockIn(wxCommandEvent& event) {
    wxMessageBox("Running the Lock in Amplifier");
    wxExecute("./lock_in_amplifier");
    wxMessageBox("Finished");
}
