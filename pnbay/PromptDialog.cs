using System;
using System.Drawing;
using System.Windows.Forms;

namespace pnbay
{
    public class PromptDialog : Form
    {
        private TextBox txtPrompt;
        private Button btnSubmit;
        public string UserPrompt { get; private set; }

        public PromptDialog()
        {
            this.Text = "Trợ lý AI - pnbay";
            this.Size = new Size(500, 150);
            this.StartPosition = FormStartPosition.CenterScreen;
            this.FormBorderStyle = FormBorderStyle.FixedDialog;
            this.MaximizeBox = false;
            this.MinimizeBox = false;

            Label lbl = new Label();
            lbl.Text = "Nhập yêu cầu vẽ (VD: vẽ đường thẳng dài 10m tại gốc tọa độ theo trục y):";
            lbl.Location = new Point(15, 10);
            lbl.AutoSize = true;

            txtPrompt = new TextBox();
            txtPrompt.Location = new Point(15, 35);
            txtPrompt.Size = new Size(450, 22);
            
            btnSubmit = new Button();
            btnSubmit.Text = "Thực hiện";
            btnSubmit.Location = new Point(365, 65);
            btnSubmit.Size = new Size(100, 30);
            btnSubmit.Click += BtnSubmit_Click;

            this.Controls.Add(lbl);
            this.Controls.Add(txtPrompt);
            this.Controls.Add(btnSubmit);
            this.AcceptButton = btnSubmit; // Bấm Enter để gửi

            // WinForms không tự đưa con trỏ vào ô nhập khi mở dialog — nếu không focus
            // thủ công, người dùng gõ ngay có thể bị rơi mất ký tự, dẫn đến bấm "Thực hiện"
            // với ô trống và bị chặn bởi thông báo "Vui lòng nhập yêu cầu!".
            this.Shown += (s, e) => txtPrompt.Focus();
        }

        private void BtnSubmit_Click(object sender, EventArgs e)
        {
            if (string.IsNullOrWhiteSpace(txtPrompt.Text))
            {
                MessageBox.Show("Vui lòng nhập yêu cầu!", "Lỗi", MessageBoxButtons.OK, MessageBoxIcon.Warning);
                return;
            }
            UserPrompt = txtPrompt.Text;
            this.DialogResult = DialogResult.OK;
            this.Close();
        }
    }
}
