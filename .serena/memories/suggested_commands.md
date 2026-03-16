Useful commands for this project on Darwin:
- git status -sb
- rg <pattern> <path>
- python twocomms/manage.py <command>
- pip install -r twocomms/requirements.txt
- npm install
- npm run build:css
- docker compose up -d
Deployment pattern from README: sshpass -p "$DEPLOY_PASS" ssh -o StrictHostKeyChecking=no "$DEPLOY_USER@$DEPLOY_HOST" "bash -lc 'source /path/to/venv/bin/activate && cd /path/to/project && git pull'"