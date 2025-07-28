# AWS Automation Tamer (AAT)

> **Tame your AWS chaos. Automate with ease.**

**AWS Automation Tamer** (a.k.a. **AWS Tamer**, shorthand CLI command **`aat`**) is an open‑source command‑line interface designed to simplify and automate common AWS operations across multiple accounts. Whether you need on‑demand EC2 backups, instance management, or quick retrieval of resource information, AAT makes it fast and intuitive.

## 💻 Installation

```bash
# From PyPI (planned)
pip install aws-tamer

# From source
git clone https://github.com/your-username/aws-tamer.git
cd aws-tamer
pip install .
```

## 🔧 Usage

After installation, you can run commands using either:

```bash
aat <service> <action> [arguments]
# or
aws-tamer <service> <action> [arguments]
```

### Example: EC2 Backup

```bash
# Create a 7‑day retention backup of 'my-server'
aat ec2 backup my-server TCK-1234 -r 7
```

This will:

1. Discover the instance named `my-server` across all configured AWS accounts.
2. Create an AMI snapshot tagged with ticket `TCK-1234`.
3. Set retention to 7 days.

## 📚 Available Commands

Use `aat help` or `aws-tamer help` to list available services and actions:

```
aat help
```

## 🛣️ Roadmap

* To be added

Contributions welcome! See [CONTRIBUTING.md](CONTRIBUTING.md).

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch: `git checkout -b feature/your-feature`
3. Commit your changes: `git commit -am 'Add some feature'`
4. Push to the branch: `git push origin feature/your-feature`
5. Open a Pull Request and describe your changes

Please read [CODE\_OF\_CONDUCT.md](CODE_OF_CONDUCT.md) and [CONTRIBUTING.md](CONTRIBUTING.md) before contributing.

## 📜 License

This project is licensed under the MIT License. See [LICENSE](LICENSE) for details.

## 🏷️ Topics

```
aws
cli
devops
automation
cloud
ec2
sysadmin
infrastructure-as-code
python
multi-account
open-source
```
