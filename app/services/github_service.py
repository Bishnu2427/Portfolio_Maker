import os
import time
from github import Github, GithubException


class GitHubService:
    def __init__(self, token: str):
        self.g = Github(token)
        self.user = self.g.get_user()

    def deploy(self, portfolio_dir: str, repo_name: str) -> dict:
        try:
            repo = self.user.get_repo(repo_name)
        except GithubException:
            repo = self.user.create_repo(
                repo_name,
                description='My Portfolio — Built with PortfolioForge',
                private=False,
                auto_init=True,
            )
            time.sleep(3)

        branch = repo.default_branch
        self._push_files(repo, portfolio_dir, branch)

        try:
            repo.enable_pages(source={'branch': branch, 'path': '/'})
        except Exception as e:
            print(f'[GitHub] Pages enable note: {e}')

        username = self.user.login
        return {
            'repo_url': repo.html_url,
            'pages_url': f'https://{username}.github.io/{repo_name}',
        }

    def _push_files(self, repo, directory: str, branch: str):
        files = self._collect_files(directory)
        for rel_path, abs_path in files:
            with open(abs_path, 'rb') as f:
                content = f.read()
            commit_msg = f'Deploy {rel_path}'
            try:
                existing = repo.get_contents(rel_path, ref=branch)
                repo.update_file(rel_path, commit_msg, content, existing.sha, branch=branch)
            except GithubException:
                repo.create_file(rel_path, commit_msg, content, branch=branch)
            time.sleep(0.3)

    @staticmethod
    def _collect_files(directory: str) -> list:
        result = []
        skip = {'app.py', 'requirements.txt', 'port.txt', 'data.json'}
        for root, dirs, files in os.walk(directory):
            dirs[:] = [d for d in dirs if d not in ('__pycache__',)]
            for fname in files:
                if fname in skip or fname.endswith('.pyc'):
                    continue
                abs_path = os.path.join(root, fname)
                rel_path = os.path.relpath(abs_path, directory).replace('\\', '/')
                result.append((rel_path, abs_path))
        return result
