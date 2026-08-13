using System;
using System.Drawing;
using System.Windows.Forms;

namespace pnbay
{
    public class ChatPanelControl : UserControl
    {
        private RichTextBox txtHistory;
        private TextBox txtInput;
        private Button btnSend;
        private Panel pnlBottom;
        private Timer thinkingTimer;
        private int thinkingDotsAt = -1;
        private int thinkingDotsCount;

        public event Action<string> SendRequested;

        public ChatPanelControl()
        {
            this.Dock = DockStyle.Fill;

            txtHistory = new RichTextBox();
            txtHistory.Dock = DockStyle.Fill;
            txtHistory.ReadOnly = true;
            txtHistory.BackColor = Color.White;
            txtHistory.BorderStyle = BorderStyle.None;

            pnlBottom = new Panel();
            pnlBottom.Dock = DockStyle.Bottom;
            pnlBottom.Height = 60;
            pnlBottom.Padding = new Padding(6);

            txtInput = new TextBox();
            txtInput.Dock = DockStyle.Fill;
            txtInput.KeyDown += TxtInput_KeyDown;

            btnSend = new Button();
            btnSend.Text = "Gửi";
            btnSend.Dock = DockStyle.Right;
            btnSend.Width = 70;
            btnSend.Click += (s, e) => TrySend();

            pnlBottom.Controls.Add(txtInput);
            pnlBottom.Controls.Add(btnSend);

            this.Controls.Add(txtHistory);
            this.Controls.Add(pnlBottom);

            thinkingTimer = new Timer();
            thinkingTimer.Interval = 400;
            thinkingTimer.Tick += ThinkingTimer_Tick;
        }

        protected override void Dispose(bool disposing)
        {
            if (disposing)
            {
                thinkingTimer?.Stop();
                thinkingTimer?.Dispose();
            }
            base.Dispose(disposing);
        }

        private void TxtInput_KeyDown(object sender, KeyEventArgs e)
        {
            if (e.KeyCode == Keys.Enter)
            {
                e.SuppressKeyPress = true;
                TrySend();
            }
        }

        private void TrySend()
        {
            string text = txtInput.Text.Trim();
            if (string.IsNullOrEmpty(text)) return;
            txtInput.Clear();
            SendRequested?.Invoke(text);
        }

        public void AppendMessage(string who, string text)
        {
            if (this.InvokeRequired)
            {
                this.Invoke(new Action(() => AppendMessage(who, text)));
                return;
            }
            txtHistory.SelectionStart = txtHistory.TextLength;
            txtHistory.SelectionLength = 0;
            txtHistory.SelectionFont = new Font(txtHistory.Font, FontStyle.Bold);
            txtHistory.AppendText($"{who}: ");
            txtHistory.SelectionFont = new Font(txtHistory.Font, FontStyle.Regular);
            txtHistory.AppendText($"{text}\n\n");
            txtHistory.SelectionStart = txtHistory.TextLength;
            txtHistory.ScrollToCaret();
        }

        public void SetBusy(bool busy)
        {
            if (this.InvokeRequired)
            {
                this.Invoke(new Action(() => SetBusy(busy)));
                return;
            }
            txtInput.Enabled = !busy;
            btnSend.Enabled = !busy;
        }

        /// <summary>Hiện "{who}: {baseText}" kèm chấm động (. .. ...) lặp lại cho tới khi StopThinking().</summary>
        public void StartThinking(string who, string baseText)
        {
            if (this.InvokeRequired)
            {
                this.Invoke(new Action(() => StartThinking(who, baseText)));
                return;
            }
            txtHistory.SelectionStart = txtHistory.TextLength;
            txtHistory.SelectionLength = 0;
            txtHistory.SelectionFont = new Font(txtHistory.Font, FontStyle.Bold);
            txtHistory.AppendText($"{who}: ");
            txtHistory.SelectionFont = new Font(txtHistory.Font, FontStyle.Regular);
            txtHistory.AppendText(baseText);

            thinkingDotsAt = txtHistory.TextLength;
            thinkingDotsCount = 0;
            txtHistory.AppendText("\n\n");
            txtHistory.SelectionStart = txtHistory.TextLength;
            txtHistory.ScrollToCaret();

            thinkingTimer.Start();
        }

        private void ThinkingTimer_Tick(object sender, EventArgs e)
        {
            if (thinkingDotsAt < 0) return;
            thinkingDotsCount = (thinkingDotsCount + 1) % 4;
            string dots = new string('.', thinkingDotsCount);

            // Đo độ dài đoạn chấm hiện có (từ vị trí neo tới ký tự xuống dòng đầu tiên) để thay đúng phạm vi.
            string afterAnchor = txtHistory.Text.Substring(thinkingDotsAt);
            int newlineIdx = afterAnchor.IndexOf('\n');
            int selLen = newlineIdx >= 0 ? newlineIdx : afterAnchor.Length;

            txtHistory.Select(thinkingDotsAt, selLen);
            txtHistory.SelectedText = dots;
        }

        public void StopThinking()
        {
            if (this.InvokeRequired)
            {
                this.Invoke(new Action(() => StopThinking()));
                return;
            }
            thinkingTimer.Stop();
            thinkingDotsAt = -1;
        }
    }
}
