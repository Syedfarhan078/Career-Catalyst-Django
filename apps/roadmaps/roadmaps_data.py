"""
Pre-built career roadmap data for 15 career paths.
Each path contains weekly milestones with topics and resource links.
"""

CAREER_PATHS = [
    {
        "name": "Software Engineer",
        "slug": "software-engineer",
        "icon": "bi-code-slash",
        "description": "Master full-stack software development from fundamentals to system design and deployment.",
        "estimated_weeks": 12,
        "difficulty": "Intermediate",
        "milestones": [
            {"week": 1, "title": "Programming Fundamentals", "level": "Beginner", "topics": [
                {"title": "Python Basics & Data Types", "desc": "Variables, strings, lists, dictionaries, loops, conditionals.", "url": "https://docs.python.org/3/tutorial/", "type": "Documentation", "hours": 4},
                {"title": "Functions & Modules", "desc": "Writing reusable functions, imports, and packages.", "url": "https://www.youtube.com/watch?v=9Os0o3wzS_I", "type": "Video", "hours": 3},
                {"title": "Object-Oriented Programming", "desc": "Classes, inheritance, polymorphism, encapsulation.", "url": "https://realpython.com/python3-object-oriented-programming/", "type": "Article", "hours": 4},
            ]},
            {"week": 2, "title": "Data Structures & Algorithms", "level": "Beginner", "topics": [
                {"title": "Arrays, Stacks & Queues", "desc": "Linear data structures and their operations.", "url": "https://www.geeksforgeeks.org/data-structures/", "type": "Article", "hours": 4},
                {"title": "Sorting & Searching", "desc": "Binary search, merge sort, quick sort.", "url": "https://visualgo.net/en", "type": "Article", "hours": 4},
                {"title": "Trees & Graphs Basics", "desc": "Binary trees, BFS, DFS traversals.", "url": "https://www.youtube.com/watch?v=oSWTXtMglKE", "type": "Video", "hours": 5},
            ]},
            {"week": 3, "title": "Version Control & Git", "level": "Beginner", "topics": [
                {"title": "Git Fundamentals", "desc": "Init, add, commit, branch, merge, rebase.", "url": "https://git-scm.com/doc", "type": "Documentation", "hours": 3},
                {"title": "GitHub Collaboration", "desc": "Pull requests, code reviews, issues, forks.", "url": "https://docs.github.com/en/get-started", "type": "Documentation", "hours": 2},
                {"title": "Git Branching Strategies", "desc": "GitFlow, trunk-based development.", "url": "https://www.atlassian.com/git/tutorials/comparing-workflows", "type": "Article", "hours": 2},
            ]},
            {"week": 4, "title": "Web Development Basics", "level": "Beginner", "topics": [
                {"title": "HTML5 & Semantic Elements", "desc": "Structure web pages with semantic HTML.", "url": "https://developer.mozilla.org/en-US/docs/Web/HTML", "type": "Documentation", "hours": 3},
                {"title": "CSS3 & Responsive Design", "desc": "Flexbox, Grid, media queries.", "url": "https://web.dev/learn/css/", "type": "Course", "hours": 4},
                {"title": "JavaScript Essentials", "desc": "DOM manipulation, events, ES6+ features.", "url": "https://javascript.info/", "type": "Article", "hours": 5},
            ]},
            {"week": 5, "title": "Backend Development", "level": "Intermediate", "topics": [
                {"title": "REST API Design", "desc": "HTTP methods, status codes, RESTful principles.", "url": "https://restfulapi.net/", "type": "Article", "hours": 3},
                {"title": "Django / Flask Framework", "desc": "Build server-side applications with Python.", "url": "https://docs.djangoproject.com/en/stable/intro/tutorial01/", "type": "Documentation", "hours": 5},
                {"title": "Authentication & Authorization", "desc": "JWT, OAuth, session-based auth.", "url": "https://www.youtube.com/watch?v=7Q17ubqLfaM", "type": "Video", "hours": 3},
            ]},
            {"week": 6, "title": "Databases", "level": "Intermediate", "topics": [
                {"title": "SQL Fundamentals", "desc": "SELECT, JOIN, GROUP BY, subqueries.", "url": "https://www.w3schools.com/sql/", "type": "Article", "hours": 4},
                {"title": "PostgreSQL Deep Dive", "desc": "Indexes, transactions, query optimization.", "url": "https://www.postgresql.org/docs/current/tutorial.html", "type": "Documentation", "hours": 4},
                {"title": "NoSQL (MongoDB)", "desc": "Document databases, aggregation pipeline.", "url": "https://university.mongodb.com/", "type": "Course", "hours": 3},
            ]},
            {"week": 7, "title": "Frontend Frameworks", "level": "Intermediate", "topics": [
                {"title": "React.js Basics", "desc": "Components, state, props, hooks.", "url": "https://react.dev/learn", "type": "Documentation", "hours": 5},
                {"title": "State Management", "desc": "Context API, Redux basics.", "url": "https://redux.js.org/tutorials/essentials/part-1-overview-concepts", "type": "Documentation", "hours": 3},
                {"title": "API Integration", "desc": "Fetch, Axios, handling async data.", "url": "https://www.youtube.com/watch?v=bYFYF2GnMy8", "type": "Video", "hours": 3},
            ]},
            {"week": 8, "title": "Testing & Quality", "level": "Intermediate", "topics": [
                {"title": "Unit Testing", "desc": "pytest, unittest, test-driven development.", "url": "https://docs.pytest.org/en/stable/", "type": "Documentation", "hours": 3},
                {"title": "Integration Testing", "desc": "Testing APIs, database interactions.", "url": "https://realpython.com/python-testing/", "type": "Article", "hours": 3},
                {"title": "Code Quality Tools", "desc": "Linters, formatters, type checking.", "url": "https://pylint.readthedocs.io/en/stable/", "type": "Documentation", "hours": 2},
            ]},
            {"week": 9, "title": "DevOps Essentials", "level": "Intermediate", "topics": [
                {"title": "Docker Basics", "desc": "Containers, Dockerfiles, docker-compose.", "url": "https://docs.docker.com/get-started/", "type": "Documentation", "hours": 4},
                {"title": "CI/CD Pipelines", "desc": "GitHub Actions, automated testing & deployment.", "url": "https://docs.github.com/en/actions", "type": "Documentation", "hours": 3},
                {"title": "Linux Command Line", "desc": "Essential commands, shell scripting basics.", "url": "https://linuxcommand.org/", "type": "Article", "hours": 3},
            ]},
            {"week": 10, "title": "System Design Basics", "level": "Advanced", "topics": [
                {"title": "Scalability Concepts", "desc": "Load balancing, caching, CDN, database sharding.", "url": "https://github.com/donnemartin/system-design-primer", "type": "Article", "hours": 5},
                {"title": "Microservices Architecture", "desc": "Service decomposition, API gateway, message queues.", "url": "https://microservices.io/", "type": "Article", "hours": 4},
                {"title": "Design Patterns", "desc": "Singleton, Factory, Observer, Strategy patterns.", "url": "https://refactoring.guru/design-patterns", "type": "Article", "hours": 4},
            ]},
            {"week": 11, "title": "Cloud & Deployment", "level": "Advanced", "topics": [
                {"title": "AWS / GCP Basics", "desc": "EC2, S3, Lambda, Cloud Functions.", "url": "https://aws.amazon.com/getting-started/", "type": "Documentation", "hours": 4},
                {"title": "Deployment Strategies", "desc": "Blue-green, canary, rolling deployments.", "url": "https://www.youtube.com/watch?v=AWVTKBUnoIg", "type": "Video", "hours": 3},
                {"title": "Monitoring & Logging", "desc": "Application performance monitoring, log aggregation.", "url": "https://grafana.com/docs/", "type": "Documentation", "hours": 3},
            ]},
            {"week": 12, "title": "Career Preparation", "level": "Advanced", "topics": [
                {"title": "Technical Interview Prep", "desc": "LeetCode patterns, mock interviews.", "url": "https://leetcode.com/explore/", "type": "Course", "hours": 5},
                {"title": "System Design Interviews", "desc": "Practice designing real-world systems.", "url": "https://www.youtube.com/watch?v=UzLMhqg3_Wc", "type": "Video", "hours": 4},
                {"title": "Portfolio & Resume", "desc": "Showcase projects, open-source contributions.", "url": "https://www.freecodecamp.org/news/how-to-build-a-developer-portfolio/", "type": "Article", "hours": 2},
            ]},
        ]
    },
    {
        "name": "Data Scientist",
        "slug": "data-scientist",
        "icon": "bi-graph-up",
        "description": "Learn statistical analysis, machine learning, and data visualization to extract insights from data.",
        "estimated_weeks": 12,
        "difficulty": "Intermediate",
        "milestones": [
            {"week": 1, "title": "Python for Data Science", "level": "Beginner", "topics": [
                {"title": "NumPy Fundamentals", "desc": "Arrays, broadcasting, vectorized operations.", "url": "https://numpy.org/doc/stable/user/quickstart.html", "type": "Documentation", "hours": 4},
                {"title": "Pandas DataFrames", "desc": "Data loading, cleaning, manipulation, groupby.", "url": "https://pandas.pydata.org/docs/getting_started/", "type": "Documentation", "hours": 5},
                {"title": "Matplotlib & Seaborn", "desc": "Data visualization, plots, charts, heatmaps.", "url": "https://matplotlib.org/stable/tutorials/", "type": "Documentation", "hours": 3},
            ]},
            {"week": 2, "title": "Statistics & Probability", "level": "Beginner", "topics": [
                {"title": "Descriptive Statistics", "desc": "Mean, median, mode, variance, standard deviation.", "url": "https://www.khanacademy.org/math/statistics-probability", "type": "Course", "hours": 4},
                {"title": "Probability Distributions", "desc": "Normal, binomial, Poisson distributions.", "url": "https://www.youtube.com/watch?v=OvTEhNL96v0", "type": "Video", "hours": 3},
                {"title": "Hypothesis Testing", "desc": "t-tests, p-values, confidence intervals.", "url": "https://www.statisticshowto.com/probability-and-statistics/hypothesis-testing/", "type": "Article", "hours": 4},
            ]},
            {"week": 3, "title": "Exploratory Data Analysis", "level": "Beginner", "topics": [
                {"title": "Data Cleaning Techniques", "desc": "Handling missing values, outliers, duplicates.", "url": "https://www.kaggle.com/learn/data-cleaning", "type": "Course", "hours": 4},
                {"title": "Feature Engineering", "desc": "Creating new features, encoding, scaling.", "url": "https://www.kaggle.com/learn/feature-engineering", "type": "Course", "hours": 4},
                {"title": "EDA with Real Datasets", "desc": "Practice on Kaggle datasets end-to-end.", "url": "https://www.kaggle.com/datasets", "type": "Course", "hours": 4},
            ]},
            {"week": 4, "title": "Machine Learning Fundamentals", "level": "Intermediate", "topics": [
                {"title": "Linear & Logistic Regression", "desc": "Supervised learning foundations.", "url": "https://scikit-learn.org/stable/supervised_learning.html", "type": "Documentation", "hours": 4},
                {"title": "Decision Trees & Random Forests", "desc": "Tree-based models, ensemble methods.", "url": "https://www.youtube.com/watch?v=J4Wdy0Wc_xQ", "type": "Video", "hours": 4},
                {"title": "Model Evaluation Metrics", "desc": "Accuracy, precision, recall, F1, ROC-AUC.", "url": "https://scikit-learn.org/stable/modules/model_evaluation.html", "type": "Documentation", "hours": 3},
            ]},
            {"week": 5, "title": "Advanced ML", "level": "Intermediate", "topics": [
                {"title": "SVM & KNN", "desc": "Support vector machines, k-nearest neighbors.", "url": "https://scikit-learn.org/stable/modules/svm.html", "type": "Documentation", "hours": 3},
                {"title": "Clustering (K-Means, DBSCAN)", "desc": "Unsupervised learning algorithms.", "url": "https://www.youtube.com/watch?v=4b5d3muPQmA", "type": "Video", "hours": 3},
                {"title": "Dimensionality Reduction", "desc": "PCA, t-SNE for high-dimensional data.", "url": "https://scikit-learn.org/stable/modules/decomposition.html", "type": "Documentation", "hours": 3},
            ]},
            {"week": 6, "title": "SQL for Data Science", "level": "Intermediate", "topics": [
                {"title": "Complex Queries", "desc": "Window functions, CTEs, subqueries.", "url": "https://mode.com/sql-tutorial/", "type": "Course", "hours": 4},
                {"title": "Data Warehousing Concepts", "desc": "Star schema, fact tables, dimension tables.", "url": "https://www.youtube.com/watch?v=lWPiSZf7-uQ", "type": "Video", "hours": 3},
            ]},
            {"week": 7, "title": "Deep Learning Intro", "level": "Advanced", "topics": [
                {"title": "Neural Networks Basics", "desc": "Perceptron, activation functions, backpropagation.", "url": "https://www.youtube.com/watch?v=aircAruvnKk", "type": "Video", "hours": 4},
                {"title": "TensorFlow / PyTorch Basics", "desc": "Tensors, models, training loops.", "url": "https://pytorch.org/tutorials/beginner/deep_learning_60min_blitz.html", "type": "Documentation", "hours": 5},
            ]},
            {"week": 8, "title": "NLP & Computer Vision", "level": "Advanced", "topics": [
                {"title": "Text Processing & NLP", "desc": "Tokenization, sentiment analysis, TF-IDF.", "url": "https://huggingface.co/learn/nlp-course/", "type": "Course", "hours": 5},
                {"title": "Image Classification", "desc": "CNNs, transfer learning with pretrained models.", "url": "https://www.tensorflow.org/tutorials/images/classification", "type": "Documentation", "hours": 4},
            ]},
            {"week": 9, "title": "Data Storytelling & BI Tools", "level": "Intermediate", "topics": [
                {"title": "Tableau / Power BI", "desc": "Creating dashboards and interactive visualizations.", "url": "https://www.tableau.com/learn/training", "type": "Course", "hours": 4},
                {"title": "Data Storytelling", "desc": "Communicating insights effectively.", "url": "https://www.youtube.com/watch?v=8EMW7io4rSI", "type": "Video", "hours": 2},
            ]},
            {"week": 10, "title": "Capstone Project", "level": "Advanced", "topics": [
                {"title": "End-to-End ML Project", "desc": "Problem definition to deployment.", "url": "https://www.kaggle.com/competitions", "type": "Course", "hours": 8},
                {"title": "Model Deployment", "desc": "Flask/FastAPI serving, Docker containerization.", "url": "https://www.youtube.com/watch?v=SQ8bMqvY4SQ", "type": "Video", "hours": 4},
            ]},
        ]
    },
    {
        "name": "ML Engineer",
        "slug": "ml-engineer",
        "icon": "bi-cpu",
        "description": "Build production-grade machine learning systems with MLOps, model serving, and scalable pipelines.",
        "estimated_weeks": 12,
        "difficulty": "Advanced",
        "milestones": [
            {"week": 1, "title": "Python & ML Foundations", "level": "Beginner", "topics": [
                {"title": "Advanced Python", "desc": "Decorators, generators, context managers.", "url": "https://realpython.com/", "type": "Article", "hours": 4},
                {"title": "NumPy & Pandas Mastery", "desc": "Optimized data operations at scale.", "url": "https://numpy.org/doc/stable/", "type": "Documentation", "hours": 4},
                {"title": "Scikit-Learn Pipeline", "desc": "Pipelines, transformers, cross-validation.", "url": "https://scikit-learn.org/stable/modules/compose.html", "type": "Documentation", "hours": 3},
            ]},
            {"week": 2, "title": "Deep Learning Frameworks", "level": "Intermediate", "topics": [
                {"title": "PyTorch Deep Dive", "desc": "Custom datasets, dataloaders, training loops.", "url": "https://pytorch.org/tutorials/", "type": "Documentation", "hours": 5},
                {"title": "TensorFlow & Keras", "desc": "Sequential models, functional API, callbacks.", "url": "https://www.tensorflow.org/tutorials", "type": "Documentation", "hours": 5},
            ]},
            {"week": 3, "title": "Computer Vision", "level": "Intermediate", "topics": [
                {"title": "CNNs & Image Classification", "desc": "Convolutional layers, pooling, architectures.", "url": "https://cs231n.github.io/", "type": "Article", "hours": 5},
                {"title": "Object Detection", "desc": "YOLO, SSD, Faster R-CNN.", "url": "https://www.youtube.com/watch?v=NM6lrjlAKDc", "type": "Video", "hours": 4},
                {"title": "Transfer Learning", "desc": "Fine-tuning pretrained models.", "url": "https://pytorch.org/tutorials/beginner/transfer_learning_tutorial.html", "type": "Documentation", "hours": 3},
            ]},
            {"week": 4, "title": "Natural Language Processing", "level": "Intermediate", "topics": [
                {"title": "Text Preprocessing", "desc": "Tokenization, stemming, lemmatization.", "url": "https://www.nltk.org/", "type": "Documentation", "hours": 3},
                {"title": "Transformers & BERT", "desc": "Attention mechanism, Hugging Face models.", "url": "https://huggingface.co/learn/nlp-course/", "type": "Course", "hours": 5},
                {"title": "Text Generation & LLMs", "desc": "GPT, prompt engineering, fine-tuning.", "url": "https://platform.openai.com/docs/guides", "type": "Documentation", "hours": 4},
            ]},
            {"week": 5, "title": "MLOps & Experiment Tracking", "level": "Advanced", "topics": [
                {"title": "MLflow & W&B", "desc": "Experiment tracking, model registry.", "url": "https://mlflow.org/docs/latest/index.html", "type": "Documentation", "hours": 4},
                {"title": "Feature Stores", "desc": "Feast, feature engineering pipelines.", "url": "https://feast.dev/", "type": "Documentation", "hours": 3},
                {"title": "Model Versioning (DVC)", "desc": "Data version control for ML projects.", "url": "https://dvc.org/doc", "type": "Documentation", "hours": 3},
            ]},
            {"week": 6, "title": "Model Deployment", "level": "Advanced", "topics": [
                {"title": "FastAPI for ML Serving", "desc": "Build REST APIs for model inference.", "url": "https://fastapi.tiangolo.com/tutorial/", "type": "Documentation", "hours": 4},
                {"title": "Docker & Kubernetes for ML", "desc": "Containerize and orchestrate ML services.", "url": "https://kubernetes.io/docs/tutorials/", "type": "Documentation", "hours": 5},
                {"title": "Cloud ML Services", "desc": "AWS SageMaker, GCP Vertex AI, Azure ML.", "url": "https://aws.amazon.com/sagemaker/", "type": "Documentation", "hours": 4},
            ]},
            {"week": 7, "title": "Distributed Training", "level": "Advanced", "topics": [
                {"title": "Data Parallelism", "desc": "Multi-GPU training with PyTorch DDP.", "url": "https://pytorch.org/tutorials/intermediate/ddp_tutorial.html", "type": "Documentation", "hours": 5},
                {"title": "Model Optimization", "desc": "Quantization, pruning, knowledge distillation.", "url": "https://pytorch.org/docs/stable/quantization.html", "type": "Documentation", "hours": 4},
            ]},
            {"week": 8, "title": "ML System Design", "level": "Advanced", "topics": [
                {"title": "End-to-End ML Pipelines", "desc": "Data ingestion to model monitoring.", "url": "https://www.youtube.com/watch?v=nU8DcBF-qo4", "type": "Video", "hours": 5},
                {"title": "A/B Testing for ML", "desc": "Online experiments, statistical significance.", "url": "https://exp-platform.com/Documents/2013-02-CUPED-ImprovingSensitivityOfControlledExperiments.pdf", "type": "Article", "hours": 3},
                {"title": "ML Interview Preparation", "desc": "ML system design questions and case studies.", "url": "https://huyenchip.com/ml-interviews-book/", "type": "Article", "hours": 4},
            ]},
        ]
    },
    {
        "name": "DevOps Engineer",
        "slug": "devops-engineer",
        "icon": "bi-gear-wide-connected",
        "description": "Automate infrastructure, build CI/CD pipelines, and manage cloud-native deployments.",
        "estimated_weeks": 10,
        "difficulty": "Intermediate",
        "milestones": [
            {"week": 1, "title": "Linux & Networking", "level": "Beginner", "topics": [
                {"title": "Linux Administration", "desc": "Users, permissions, processes, services.", "url": "https://linuxjourney.com/", "type": "Course", "hours": 5},
                {"title": "Networking Fundamentals", "desc": "TCP/IP, DNS, HTTP, firewalls.", "url": "https://www.youtube.com/watch?v=3QhU9jd03a0", "type": "Video", "hours": 4},
                {"title": "Shell Scripting", "desc": "Bash automation, cron jobs.", "url": "https://www.shellscript.sh/", "type": "Article", "hours": 3},
            ]},
            {"week": 2, "title": "Version Control & Git", "level": "Beginner", "topics": [
                {"title": "Git Advanced", "desc": "Cherry-pick, rebase, bisect, hooks.", "url": "https://git-scm.com/book/en/v2", "type": "Documentation", "hours": 3},
                {"title": "Branching Strategies", "desc": "GitFlow, GitHub Flow, trunk-based.", "url": "https://www.atlassian.com/git/tutorials", "type": "Article", "hours": 2},
            ]},
            {"week": 3, "title": "Containers & Docker", "level": "Intermediate", "topics": [
                {"title": "Docker Deep Dive", "desc": "Multi-stage builds, networking, volumes.", "url": "https://docs.docker.com/", "type": "Documentation", "hours": 5},
                {"title": "Docker Compose", "desc": "Multi-container orchestration.", "url": "https://docs.docker.com/compose/", "type": "Documentation", "hours": 3},
                {"title": "Container Security", "desc": "Image scanning, least-privilege containers.", "url": "https://snyk.io/learn/container-security/", "type": "Article", "hours": 3},
            ]},
            {"week": 4, "title": "CI/CD Pipelines", "level": "Intermediate", "topics": [
                {"title": "GitHub Actions", "desc": "Workflows, jobs, artifacts.", "url": "https://docs.github.com/en/actions", "type": "Documentation", "hours": 4},
                {"title": "Jenkins", "desc": "Pipeline-as-code, plugins.", "url": "https://www.jenkins.io/doc/tutorials/", "type": "Documentation", "hours": 4},
                {"title": "ArgoCD & GitOps", "desc": "Declarative deployments with Git.", "url": "https://argo-cd.readthedocs.io/en/stable/", "type": "Documentation", "hours": 3},
            ]},
            {"week": 5, "title": "Kubernetes", "level": "Intermediate", "topics": [
                {"title": "Kubernetes Core Concepts", "desc": "Pods, services, deployments, ConfigMaps.", "url": "https://kubernetes.io/docs/tutorials/", "type": "Documentation", "hours": 5},
                {"title": "Helm Charts", "desc": "Package Kubernetes applications.", "url": "https://helm.sh/docs/intro/quickstart/", "type": "Documentation", "hours": 3},
                {"title": "Kubernetes Networking", "desc": "Ingress, load balancers, service mesh.", "url": "https://www.youtube.com/watch?v=GhZi4DxaxxE", "type": "Video", "hours": 4},
            ]},
            {"week": 6, "title": "Cloud Platforms", "level": "Intermediate", "topics": [
                {"title": "AWS Core Services", "desc": "EC2, S3, RDS, Lambda, IAM.", "url": "https://aws.amazon.com/getting-started/", "type": "Documentation", "hours": 5},
                {"title": "Infrastructure as Code (Terraform)", "desc": "Declarative infrastructure management.", "url": "https://developer.hashicorp.com/terraform/tutorials", "type": "Documentation", "hours": 5},
            ]},
            {"week": 7, "title": "Monitoring & Observability", "level": "Advanced", "topics": [
                {"title": "Prometheus & Grafana", "desc": "Metrics collection and dashboarding.", "url": "https://prometheus.io/docs/introduction/overview/", "type": "Documentation", "hours": 4},
                {"title": "ELK Stack", "desc": "Elasticsearch, Logstash, Kibana for log analysis.", "url": "https://www.elastic.co/guide/index.html", "type": "Documentation", "hours": 4},
                {"title": "Alerting & Incident Response", "desc": "PagerDuty, on-call, SLAs.", "url": "https://sre.google/sre-book/table-of-contents/", "type": "Article", "hours": 3},
            ]},
            {"week": 8, "title": "Security & SRE", "level": "Advanced", "topics": [
                {"title": "DevSecOps", "desc": "SAST, DAST, secrets management.", "url": "https://owasp.org/www-project-devsecops-guideline/", "type": "Article", "hours": 4},
                {"title": "Site Reliability Engineering", "desc": "SLIs, SLOs, error budgets, toil reduction.", "url": "https://sre.google/sre-book/table-of-contents/", "type": "Article", "hours": 5},
            ]},
        ]
    },
    {
        "name": "Product Manager",
        "slug": "product-manager",
        "icon": "bi-kanban",
        "description": "Drive product strategy, user research, and cross-functional team leadership.",
        "estimated_weeks": 10,
        "difficulty": "Beginner",
        "milestones": [
            {"week": 1, "title": "Product Thinking", "level": "Beginner", "topics": [
                {"title": "What is Product Management?", "desc": "Role, responsibilities, and PM mindset.", "url": "https://www.youtube.com/watch?v=502ILHjX9EE", "type": "Video", "hours": 2},
                {"title": "User-Centric Design", "desc": "Understanding user needs and jobs-to-be-done.", "url": "https://www.intercom.com/books/jobs-to-be-done", "type": "Article", "hours": 3},
                {"title": "Product Lifecycle", "desc": "Ideation to sunset, growth frameworks.", "url": "https://www.productplan.com/learn/product-management-frameworks/", "type": "Article", "hours": 3},
            ]},
            {"week": 2, "title": "User Research", "level": "Beginner", "topics": [
                {"title": "User Interviews", "desc": "Conducting effective interviews and surveys.", "url": "https://www.nngroup.com/articles/user-interviews/", "type": "Article", "hours": 3},
                {"title": "Persona Creation", "desc": "Building user personas from research data.", "url": "https://www.youtube.com/watch?v=u44pBnAn7cM", "type": "Video", "hours": 2},
                {"title": "Journey Mapping", "desc": "Mapping the customer experience end-to-end.", "url": "https://www.nngroup.com/articles/customer-journey-mapping/", "type": "Article", "hours": 3},
            ]},
            {"week": 3, "title": "Product Strategy", "level": "Intermediate", "topics": [
                {"title": "Competitive Analysis", "desc": "Market research, SWOT, Porter's Five Forces.", "url": "https://www.productplan.com/learn/product-strategy/", "type": "Article", "hours": 3},
                {"title": "Roadmap Planning", "desc": "Feature prioritization, OKRs, themes.", "url": "https://www.youtube.com/watch?v=Eber1l1MNvQ", "type": "Video", "hours": 3},
                {"title": "Metrics & KPIs", "desc": "North Star Metric, AARRR, cohort analysis.", "url": "https://www.reforge.com/", "type": "Article", "hours": 4},
            ]},
            {"week": 4, "title": "Agile & Scrum", "level": "Intermediate", "topics": [
                {"title": "Scrum Framework", "desc": "Sprints, ceremonies, roles.", "url": "https://scrumguides.org/scrum-guide.html", "type": "Documentation", "hours": 3},
                {"title": "Writing User Stories", "desc": "Acceptance criteria, story points.", "url": "https://www.atlassian.com/agile/project-management/user-stories", "type": "Article", "hours": 2},
                {"title": "Backlog Management", "desc": "Prioritization frameworks: RICE, MoSCoW.", "url": "https://www.intercom.com/blog/rice-simple-prioritization-for-product-managers/", "type": "Article", "hours": 3},
            ]},
            {"week": 5, "title": "Data-Driven Decisions", "level": "Intermediate", "topics": [
                {"title": "Product Analytics", "desc": "Mixpanel, Amplitude, Google Analytics.", "url": "https://www.youtube.com/watch?v=fTjhHrcyiQI", "type": "Video", "hours": 3},
                {"title": "A/B Testing", "desc": "Experiment design, statistical significance.", "url": "https://www.optimizely.com/optimization-glossary/ab-testing/", "type": "Article", "hours": 3},
                {"title": "SQL for PMs", "desc": "Querying data to answer product questions.", "url": "https://mode.com/sql-tutorial/", "type": "Course", "hours": 4},
            ]},
            {"week": 6, "title": "Design & Prototyping", "level": "Intermediate", "topics": [
                {"title": "Wireframing (Figma)", "desc": "Low and high-fidelity mockups.", "url": "https://www.figma.com/resources/learn-design/", "type": "Course", "hours": 4},
                {"title": "Usability Testing", "desc": "Moderated and unmoderated testing methods.", "url": "https://www.nngroup.com/articles/usability-testing-101/", "type": "Article", "hours": 3},
            ]},
            {"week": 7, "title": "Stakeholder Management", "level": "Advanced", "topics": [
                {"title": "Cross-Functional Leadership", "desc": "Working with engineering, design, marketing.", "url": "https://www.youtube.com/watch?v=JDJFojJILGo", "type": "Video", "hours": 3},
                {"title": "Presentation & Storytelling", "desc": "Communicating product vision effectively.", "url": "https://www.youtube.com/watch?v=Unzc731iCUY", "type": "Video", "hours": 2},
                {"title": "PM Interview Prep", "desc": "Product sense, estimation, strategy questions.", "url": "https://www.tryexponent.com/courses/pm-interview", "type": "Course", "hours": 5},
            ]},
        ]
    },
    {
        "name": "Frontend Developer",
        "slug": "frontend-developer",
        "icon": "bi-window-stack",
        "description": "Build beautiful, responsive, and accessible web interfaces with modern JavaScript frameworks.",
        "estimated_weeks": 10,
        "difficulty": "Beginner",
        "milestones": [
            {"week": 1, "title": "HTML & CSS Mastery", "level": "Beginner", "topics": [
                {"title": "Semantic HTML5", "desc": "Accessibility, forms, multimedia elements.", "url": "https://developer.mozilla.org/en-US/docs/Web/HTML", "type": "Documentation", "hours": 3},
                {"title": "CSS Flexbox & Grid", "desc": "Modern layout techniques.", "url": "https://css-tricks.com/snippets/css/a-guide-to-flexbox/", "type": "Article", "hours": 4},
                {"title": "Responsive Design", "desc": "Media queries, mobile-first approach.", "url": "https://web.dev/learn/design/", "type": "Course", "hours": 3},
            ]},
            {"week": 2, "title": "JavaScript Deep Dive", "level": "Beginner", "topics": [
                {"title": "ES6+ Features", "desc": "Arrow functions, destructuring, modules, promises.", "url": "https://javascript.info/", "type": "Article", "hours": 5},
                {"title": "DOM Manipulation", "desc": "Event handling, dynamic UI updates.", "url": "https://developer.mozilla.org/en-US/docs/Web/API/Document_Object_Model", "type": "Documentation", "hours": 3},
                {"title": "Async JavaScript", "desc": "Callbacks, promises, async/await, fetch API.", "url": "https://www.youtube.com/watch?v=PoRJizFvM7s", "type": "Video", "hours": 4},
            ]},
            {"week": 3, "title": "React.js", "level": "Intermediate", "topics": [
                {"title": "React Fundamentals", "desc": "JSX, components, props, state.", "url": "https://react.dev/learn", "type": "Documentation", "hours": 5},
                {"title": "React Hooks", "desc": "useState, useEffect, useContext, custom hooks.", "url": "https://react.dev/reference/react", "type": "Documentation", "hours": 4},
                {"title": "React Router", "desc": "Client-side routing, nested routes.", "url": "https://reactrouter.com/en/main/start/tutorial", "type": "Documentation", "hours": 3},
            ]},
            {"week": 4, "title": "State Management & APIs", "level": "Intermediate", "topics": [
                {"title": "Redux Toolkit", "desc": "Global state, slices, thunks.", "url": "https://redux-toolkit.js.org/introduction/getting-started", "type": "Documentation", "hours": 4},
                {"title": "REST & GraphQL", "desc": "Fetching and consuming APIs.", "url": "https://graphql.org/learn/", "type": "Documentation", "hours": 4},
            ]},
            {"week": 5, "title": "CSS Frameworks & Design Systems", "level": "Intermediate", "topics": [
                {"title": "Tailwind CSS", "desc": "Utility-first CSS framework.", "url": "https://tailwindcss.com/docs", "type": "Documentation", "hours": 4},
                {"title": "Component Libraries", "desc": "Material UI, Chakra UI, Shadcn.", "url": "https://mui.com/material-ui/getting-started/", "type": "Documentation", "hours": 3},
                {"title": "Animation Libraries", "desc": "Framer Motion, GSAP for web animations.", "url": "https://www.framer.com/motion/", "type": "Documentation", "hours": 3},
            ]},
            {"week": 6, "title": "Testing & Performance", "level": "Intermediate", "topics": [
                {"title": "Jest & React Testing Library", "desc": "Unit and integration tests.", "url": "https://testing-library.com/docs/react-testing-library/intro/", "type": "Documentation", "hours": 4},
                {"title": "Web Performance", "desc": "Lighthouse, lazy loading, code splitting.", "url": "https://web.dev/performance/", "type": "Article", "hours": 3},
                {"title": "Accessibility (a11y)", "desc": "ARIA roles, screen reader testing.", "url": "https://www.a11yproject.com/", "type": "Article", "hours": 3},
            ]},
            {"week": 7, "title": "Next.js & Deployment", "level": "Advanced", "topics": [
                {"title": "Next.js Framework", "desc": "SSR, SSG, API routes, App Router.", "url": "https://nextjs.org/docs", "type": "Documentation", "hours": 5},
                {"title": "Vercel Deployment", "desc": "Deploy frontend apps to production.", "url": "https://vercel.com/docs", "type": "Documentation", "hours": 2},
                {"title": "Frontend Portfolio", "desc": "Showcase 3-5 projects.", "url": "https://www.freecodecamp.org/news/how-to-build-a-developer-portfolio/", "type": "Article", "hours": 3},
            ]},
        ]
    },
    {
        "name": "Backend Developer",
        "slug": "backend-developer",
        "icon": "bi-server",
        "description": "Design scalable APIs, manage databases, and build robust server-side architectures.",
        "estimated_weeks": 10,
        "difficulty": "Intermediate",
        "milestones": [
            {"week": 1, "title": "Server-Side Programming", "level": "Beginner", "topics": [
                {"title": "Python / Node.js Basics", "desc": "Pick a language and learn its ecosystem.", "url": "https://docs.python.org/3/tutorial/", "type": "Documentation", "hours": 5},
                {"title": "HTTP & Web Protocols", "desc": "Request/response cycle, headers, status codes.", "url": "https://developer.mozilla.org/en-US/docs/Web/HTTP", "type": "Documentation", "hours": 3},
            ]},
            {"week": 2, "title": "Framework Mastery", "level": "Beginner", "topics": [
                {"title": "Django REST Framework", "desc": "Serializers, viewsets, routers.", "url": "https://www.django-rest-framework.org/tutorial/quickstart/", "type": "Documentation", "hours": 5},
                {"title": "Express.js / FastAPI", "desc": "Alternative backend frameworks.", "url": "https://fastapi.tiangolo.com/tutorial/", "type": "Documentation", "hours": 4},
            ]},
            {"week": 3, "title": "Database Design", "level": "Intermediate", "topics": [
                {"title": "SQL & PostgreSQL", "desc": "Schema design, normalization, indexing.", "url": "https://www.postgresql.org/docs/current/tutorial.html", "type": "Documentation", "hours": 5},
                {"title": "ORMs (Django ORM / SQLAlchemy)", "desc": "Model relationships, query optimization.", "url": "https://docs.djangoproject.com/en/stable/topics/db/", "type": "Documentation", "hours": 4},
                {"title": "Redis & Caching", "desc": "In-memory data stores, caching strategies.", "url": "https://redis.io/docs/getting-started/", "type": "Documentation", "hours": 3},
            ]},
            {"week": 4, "title": "Authentication & Security", "level": "Intermediate", "topics": [
                {"title": "JWT & OAuth2", "desc": "Token-based auth, third-party login.", "url": "https://jwt.io/introduction", "type": "Article", "hours": 3},
                {"title": "OWASP Top 10", "desc": "Common security vulnerabilities.", "url": "https://owasp.org/www-project-top-ten/", "type": "Article", "hours": 4},
                {"title": "Rate Limiting & Input Validation", "desc": "Protecting APIs from abuse.", "url": "https://www.cloudflare.com/learning/bots/what-is-rate-limiting/", "type": "Article", "hours": 2},
            ]},
            {"week": 5, "title": "API Design Patterns", "level": "Intermediate", "topics": [
                {"title": "RESTful API Best Practices", "desc": "Versioning, pagination, HATEOAS.", "url": "https://restfulapi.net/", "type": "Article", "hours": 3},
                {"title": "GraphQL", "desc": "Schema, resolvers, queries, mutations.", "url": "https://graphql.org/learn/", "type": "Documentation", "hours": 4},
                {"title": "WebSockets & Real-Time", "desc": "Chat, notifications, live updates.", "url": "https://developer.mozilla.org/en-US/docs/Web/API/WebSockets_API", "type": "Documentation", "hours": 3},
            ]},
            {"week": 6, "title": "Message Queues & Async", "level": "Advanced", "topics": [
                {"title": "Celery & Task Queues", "desc": "Background jobs, scheduled tasks.", "url": "https://docs.celeryq.dev/en/stable/getting-started/", "type": "Documentation", "hours": 4},
                {"title": "RabbitMQ / Kafka", "desc": "Event-driven architecture, pub/sub.", "url": "https://www.rabbitmq.com/tutorials", "type": "Documentation", "hours": 4},
            ]},
            {"week": 7, "title": "Scaling & Deployment", "level": "Advanced", "topics": [
                {"title": "Load Balancing & Horizontal Scaling", "desc": "Nginx, HAProxy, auto-scaling.", "url": "https://www.nginx.com/resources/glossary/load-balancing/", "type": "Article", "hours": 3},
                {"title": "Docker & CI/CD", "desc": "Containerize and deploy backend services.", "url": "https://docs.docker.com/get-started/", "type": "Documentation", "hours": 4},
                {"title": "Cloud Deployment", "desc": "Deploy on AWS, GCP, or Heroku.", "url": "https://devcenter.heroku.com/articles/getting-started-with-python", "type": "Documentation", "hours": 3},
            ]},
        ]
    },
    {
        "name": "Full Stack Developer",
        "slug": "full-stack-developer",
        "icon": "bi-layers",
        "description": "Master both frontend and backend technologies to build complete web applications.",
        "estimated_weeks": 12,
        "difficulty": "Intermediate",
        "milestones": [
            {"week": 1, "title": "Web Fundamentals", "level": "Beginner", "topics": [
                {"title": "HTML, CSS & JavaScript", "desc": "Core web technologies.", "url": "https://www.theodinproject.com/", "type": "Course", "hours": 6},
                {"title": "Git & GitHub", "desc": "Version control essentials.", "url": "https://git-scm.com/doc", "type": "Documentation", "hours": 3},
            ]},
            {"week": 2, "title": "Frontend with React", "level": "Beginner", "topics": [
                {"title": "React Essentials", "desc": "Components, hooks, routing.", "url": "https://react.dev/learn", "type": "Documentation", "hours": 5},
                {"title": "Styling with Tailwind", "desc": "Utility-first CSS.", "url": "https://tailwindcss.com/docs", "type": "Documentation", "hours": 3},
            ]},
            {"week": 3, "title": "Backend with Django", "level": "Intermediate", "topics": [
                {"title": "Django Core", "desc": "Models, views, templates, admin.", "url": "https://docs.djangoproject.com/en/stable/intro/", "type": "Documentation", "hours": 5},
                {"title": "Django REST Framework", "desc": "Build APIs consumed by React.", "url": "https://www.django-rest-framework.org/tutorial/quickstart/", "type": "Documentation", "hours": 5},
            ]},
            {"week": 4, "title": "Database & ORM", "level": "Intermediate", "topics": [
                {"title": "PostgreSQL", "desc": "Relational database design.", "url": "https://www.postgresql.org/docs/current/tutorial.html", "type": "Documentation", "hours": 4},
                {"title": "Django ORM Advanced", "desc": "Queries, annotations, aggregations.", "url": "https://docs.djangoproject.com/en/stable/topics/db/queries/", "type": "Documentation", "hours": 4},
            ]},
            {"week": 5, "title": "Authentication & Integration", "level": "Intermediate", "topics": [
                {"title": "JWT Auth Flow", "desc": "Frontend-backend auth integration.", "url": "https://jwt.io/introduction", "type": "Article", "hours": 4},
                {"title": "File Uploads & Media", "desc": "Handling file storage.", "url": "https://docs.djangoproject.com/en/stable/topics/files/", "type": "Documentation", "hours": 3},
            ]},
            {"week": 6, "title": "Full Stack Project", "level": "Intermediate", "topics": [
                {"title": "Build a Complete App", "desc": "E-commerce, blog, or social platform.", "url": "https://www.youtube.com/watch?v=c708Nf0cHrs", "type": "Video", "hours": 8},
                {"title": "Testing Both Ends", "desc": "Unit and integration tests.", "url": "https://docs.pytest.org/en/stable/", "type": "Documentation", "hours": 4},
            ]},
            {"week": 7, "title": "DevOps & Deployment", "level": "Advanced", "topics": [
                {"title": "Docker Compose", "desc": "Multi-service orchestration.", "url": "https://docs.docker.com/compose/", "type": "Documentation", "hours": 4},
                {"title": "CI/CD Pipeline", "desc": "Automated test and deploy.", "url": "https://docs.github.com/en/actions", "type": "Documentation", "hours": 3},
                {"title": "Production Deployment", "desc": "Deploy to AWS/Vercel/Railway.", "url": "https://railway.app/", "type": "Documentation", "hours": 3},
            ]},
        ]
    },
    {
        "name": "Cybersecurity Analyst",
        "slug": "cybersecurity-analyst",
        "icon": "bi-shield-lock",
        "description": "Protect systems and networks from cyber threats through ethical hacking and security analysis.",
        "estimated_weeks": 10,
        "difficulty": "Intermediate",
        "milestones": [
            {"week": 1, "title": "Security Foundations", "level": "Beginner", "topics": [
                {"title": "CIA Triad & Security Concepts", "desc": "Confidentiality, integrity, availability.", "url": "https://www.youtube.com/watch?v=z5nc6GobU8M", "type": "Video", "hours": 3},
                {"title": "Networking for Security", "desc": "Protocols, ports, firewalls, VPNs.", "url": "https://www.cybrary.it/", "type": "Course", "hours": 4},
                {"title": "Linux for Security", "desc": "Command line, logs, processes.", "url": "https://linuxjourney.com/", "type": "Course", "hours": 4},
            ]},
            {"week": 2, "title": "Ethical Hacking Basics", "level": "Beginner", "topics": [
                {"title": "OWASP Top 10", "desc": "Common web vulnerabilities.", "url": "https://owasp.org/www-project-top-ten/", "type": "Article", "hours": 4},
                {"title": "Kali Linux Tools", "desc": "Nmap, Wireshark, Metasploit basics.", "url": "https://www.kali.org/docs/", "type": "Documentation", "hours": 5},
            ]},
            {"week": 3, "title": "Web Application Security", "level": "Intermediate", "topics": [
                {"title": "SQL Injection & XSS", "desc": "Attack vectors and prevention.", "url": "https://portswigger.net/web-security", "type": "Course", "hours": 5},
                {"title": "Authentication Attacks", "desc": "Brute force, session hijacking.", "url": "https://portswigger.net/web-security/authentication", "type": "Course", "hours": 4},
            ]},
            {"week": 4, "title": "Network Security", "level": "Intermediate", "topics": [
                {"title": "Network Scanning", "desc": "Nmap, port scanning, service detection.", "url": "https://nmap.org/book/man.html", "type": "Documentation", "hours": 4},
                {"title": "Intrusion Detection", "desc": "Snort, Suricata, log analysis.", "url": "https://www.snort.org/documents", "type": "Documentation", "hours": 4},
                {"title": "Cryptography Basics", "desc": "Encryption, hashing, digital signatures.", "url": "https://www.khanacademy.org/computing/computer-science/cryptography", "type": "Course", "hours": 4},
            ]},
            {"week": 5, "title": "Incident Response", "level": "Advanced", "topics": [
                {"title": "Digital Forensics", "desc": "Evidence collection, analysis.", "url": "https://www.sans.org/cyber-security-courses/", "type": "Course", "hours": 5},
                {"title": "SIEM & Security Monitoring", "desc": "Splunk, ELK for security.", "url": "https://www.splunk.com/en_us/training.html", "type": "Course", "hours": 4},
                {"title": "CompTIA Security+ Prep", "desc": "Industry certification preparation.", "url": "https://www.comptia.org/certifications/security", "type": "Course", "hours": 5},
            ]},
        ]
    },
    {
        "name": "Cloud Architect",
        "slug": "cloud-architect",
        "icon": "bi-cloud-arrow-up",
        "description": "Design and manage scalable, secure cloud infrastructure across AWS, GCP, and Azure.",
        "estimated_weeks": 10,
        "difficulty": "Advanced",
        "milestones": [
            {"week": 1, "title": "Cloud Computing Basics", "level": "Beginner", "topics": [
                {"title": "Cloud Service Models", "desc": "IaaS, PaaS, SaaS explained.", "url": "https://aws.amazon.com/types-of-cloud-computing/", "type": "Article", "hours": 3},
                {"title": "AWS Core Services", "desc": "EC2, S3, VPC, IAM.", "url": "https://aws.amazon.com/getting-started/", "type": "Documentation", "hours": 5},
                {"title": "GCP / Azure Overview", "desc": "Multi-cloud awareness.", "url": "https://cloud.google.com/docs/overview", "type": "Documentation", "hours": 3},
            ]},
            {"week": 2, "title": "Networking in the Cloud", "level": "Intermediate", "topics": [
                {"title": "VPC & Subnets", "desc": "Network isolation, route tables.", "url": "https://docs.aws.amazon.com/vpc/latest/userguide/", "type": "Documentation", "hours": 4},
                {"title": "Load Balancers & CDN", "desc": "ALB, NLB, CloudFront.", "url": "https://aws.amazon.com/elasticloadbalancing/", "type": "Documentation", "hours": 3},
                {"title": "DNS & Route 53", "desc": "Domain management, routing policies.", "url": "https://docs.aws.amazon.com/Route53/", "type": "Documentation", "hours": 3},
            ]},
            {"week": 3, "title": "Compute & Serverless", "level": "Intermediate", "topics": [
                {"title": "EC2 & Auto Scaling", "desc": "Instance types, launch templates, ASGs.", "url": "https://docs.aws.amazon.com/autoscaling/", "type": "Documentation", "hours": 4},
                {"title": "AWS Lambda & Serverless", "desc": "Event-driven compute, API Gateway.", "url": "https://docs.aws.amazon.com/lambda/", "type": "Documentation", "hours": 4},
                {"title": "ECS & Fargate", "desc": "Container orchestration on AWS.", "url": "https://docs.aws.amazon.com/AmazonECS/", "type": "Documentation", "hours": 4},
            ]},
            {"week": 4, "title": "Storage & Databases", "level": "Intermediate", "topics": [
                {"title": "S3, EBS, EFS", "desc": "Object, block, and file storage.", "url": "https://docs.aws.amazon.com/s3/", "type": "Documentation", "hours": 4},
                {"title": "RDS & DynamoDB", "desc": "Managed relational and NoSQL databases.", "url": "https://docs.aws.amazon.com/rds/", "type": "Documentation", "hours": 4},
            ]},
            {"week": 5, "title": "Infrastructure as Code", "level": "Advanced", "topics": [
                {"title": "Terraform", "desc": "Declarative infrastructure provisioning.", "url": "https://developer.hashicorp.com/terraform/tutorials", "type": "Documentation", "hours": 5},
                {"title": "AWS CloudFormation", "desc": "Native IaC for AWS.", "url": "https://docs.aws.amazon.com/cloudformation/", "type": "Documentation", "hours": 4},
                {"title": "Pulumi", "desc": "IaC with real programming languages.", "url": "https://www.pulumi.com/docs/", "type": "Documentation", "hours": 3},
            ]},
            {"week": 6, "title": "Security & Compliance", "level": "Advanced", "topics": [
                {"title": "IAM Best Practices", "desc": "Policies, roles, least privilege.", "url": "https://docs.aws.amazon.com/IAM/latest/UserGuide/best-practices.html", "type": "Documentation", "hours": 4},
                {"title": "AWS Well-Architected Framework", "desc": "5 pillars of cloud architecture.", "url": "https://aws.amazon.com/architecture/well-architected/", "type": "Article", "hours": 4},
                {"title": "AWS Solutions Architect Prep", "desc": "Certification preparation.", "url": "https://aws.amazon.com/certification/certified-solutions-architect-associate/", "type": "Course", "hours": 6},
            ]},
        ]
    },
    {
        "name": "Mobile App Developer",
        "slug": "mobile-app-developer",
        "icon": "bi-phone",
        "description": "Build native and cross-platform mobile applications for iOS and Android.",
        "estimated_weeks": 10,
        "difficulty": "Intermediate",
        "milestones": [
            {"week": 1, "title": "Mobile Development Basics", "level": "Beginner", "topics": [
                {"title": "Mobile UI/UX Principles", "desc": "Touch interactions, navigation patterns.", "url": "https://developer.apple.com/design/human-interface-guidelines/", "type": "Documentation", "hours": 3},
                {"title": "Dart Programming", "desc": "Language fundamentals for Flutter.", "url": "https://dart.dev/guides", "type": "Documentation", "hours": 4},
            ]},
            {"week": 2, "title": "Flutter Fundamentals", "level": "Beginner", "topics": [
                {"title": "Widgets & Layouts", "desc": "MaterialApp, Scaffold, Row, Column, Stack.", "url": "https://docs.flutter.dev/development/ui/widgets-intro", "type": "Documentation", "hours": 5},
                {"title": "State Management", "desc": "setState, Provider, Riverpod.", "url": "https://docs.flutter.dev/development/data-and-backend/state-mgmt", "type": "Documentation", "hours": 4},
                {"title": "Navigation & Routing", "desc": "Named routes, GoRouter.", "url": "https://docs.flutter.dev/development/ui/navigation", "type": "Documentation", "hours": 3},
            ]},
            {"week": 3, "title": "APIs & Data", "level": "Intermediate", "topics": [
                {"title": "HTTP & REST API Calls", "desc": "dio, http package, JSON parsing.", "url": "https://docs.flutter.dev/cookbook/networking/fetch-data", "type": "Documentation", "hours": 4},
                {"title": "Local Storage", "desc": "SharedPreferences, Hive, SQLite.", "url": "https://docs.flutter.dev/cookbook/persistence", "type": "Documentation", "hours": 3},
                {"title": "Firebase Integration", "desc": "Auth, Firestore, Push Notifications.", "url": "https://firebase.google.com/docs/flutter/setup", "type": "Documentation", "hours": 5},
            ]},
            {"week": 4, "title": "Advanced Flutter", "level": "Intermediate", "topics": [
                {"title": "Animations & Transitions", "desc": "Implicit, explicit, hero animations.", "url": "https://docs.flutter.dev/development/ui/animations", "type": "Documentation", "hours": 4},
                {"title": "Platform-Specific Code", "desc": "Method channels, platform views.", "url": "https://docs.flutter.dev/development/platform-integration/platform-channels", "type": "Documentation", "hours": 3},
            ]},
            {"week": 5, "title": "Testing & Deployment", "level": "Advanced", "topics": [
                {"title": "Flutter Testing", "desc": "Widget tests, integration tests.", "url": "https://docs.flutter.dev/testing", "type": "Documentation", "hours": 4},
                {"title": "App Store Deployment", "desc": "Publishing to Play Store and App Store.", "url": "https://docs.flutter.dev/deployment", "type": "Documentation", "hours": 4},
                {"title": "CI/CD for Mobile", "desc": "Codemagic, Fastlane automation.", "url": "https://codemagic.io/", "type": "Documentation", "hours": 3},
            ]},
        ]
    },
    {
        "name": "UI/UX Designer",
        "slug": "ui-ux-designer",
        "icon": "bi-palette",
        "description": "Design intuitive user experiences and visually compelling interfaces.",
        "estimated_weeks": 10,
        "difficulty": "Beginner",
        "milestones": [
            {"week": 1, "title": "Design Thinking", "level": "Beginner", "topics": [
                {"title": "Design Thinking Process", "desc": "Empathize, Define, Ideate, Prototype, Test.", "url": "https://www.interaction-design.org/literature/article/what-is-design-thinking", "type": "Article", "hours": 3},
                {"title": "User Research Methods", "desc": "Surveys, interviews, observation.", "url": "https://www.nngroup.com/articles/which-ux-research-methods/", "type": "Article", "hours": 3},
                {"title": "Information Architecture", "desc": "Content organization, sitemaps, card sorting.", "url": "https://www.youtube.com/watch?v=OJeH519aBiI", "type": "Video", "hours": 3},
            ]},
            {"week": 2, "title": "Visual Design Fundamentals", "level": "Beginner", "topics": [
                {"title": "Color Theory", "desc": "Color palettes, contrast, accessibility.", "url": "https://www.interaction-design.org/literature/topics/color-theory", "type": "Article", "hours": 3},
                {"title": "Typography", "desc": "Font pairing, hierarchy, readability.", "url": "https://fonts.google.com/knowledge", "type": "Article", "hours": 3},
                {"title": "Layout & Composition", "desc": "Grid systems, whitespace, visual weight.", "url": "https://www.youtube.com/watch?v=a5KYlHNKQB8", "type": "Video", "hours": 3},
            ]},
            {"week": 3, "title": "Figma Mastery", "level": "Intermediate", "topics": [
                {"title": "Figma Basics", "desc": "Frames, components, auto-layout.", "url": "https://www.figma.com/resources/learn-design/", "type": "Course", "hours": 5},
                {"title": "Design Systems", "desc": "Building reusable component libraries.", "url": "https://www.designsystems.com/", "type": "Article", "hours": 4},
                {"title": "Prototyping", "desc": "Interactive prototypes, micro-interactions.", "url": "https://www.figma.com/resource-library/prototyping/", "type": "Course", "hours": 4},
            ]},
            {"week": 4, "title": "Interaction Design", "level": "Intermediate", "topics": [
                {"title": "Microinteractions", "desc": "Feedback, triggers, animations.", "url": "https://www.youtube.com/watch?v=VkLj9SqKXSI", "type": "Video", "hours": 3},
                {"title": "Usability Heuristics", "desc": "Nielsen's 10 heuristics for UI.", "url": "https://www.nngroup.com/articles/ten-usability-heuristics/", "type": "Article", "hours": 3},
                {"title": "Accessibility Design", "desc": "WCAG guidelines, inclusive design.", "url": "https://www.w3.org/WAI/fundamentals/accessibility-intro/", "type": "Article", "hours": 3},
            ]},
            {"week": 5, "title": "Portfolio & Career", "level": "Advanced", "topics": [
                {"title": "UX Case Studies", "desc": "Document your design process.", "url": "https://www.uxfol.io/", "type": "Article", "hours": 5},
                {"title": "Design Portfolio", "desc": "Showcase projects and process.", "url": "https://www.bestfolios.com/", "type": "Article", "hours": 4},
                {"title": "Design Interview Prep", "desc": "Whiteboard challenges, design critiques.", "url": "https://www.youtube.com/watch?v=gJjc1UtJpW0", "type": "Video", "hours": 3},
            ]},
        ]
    },
    {
        "name": "Data Engineer",
        "slug": "data-engineer",
        "icon": "bi-database-gear",
        "description": "Build and maintain data pipelines, warehouses, and ETL systems at scale.",
        "estimated_weeks": 10,
        "difficulty": "Advanced",
        "milestones": [
            {"week": 1, "title": "Data Engineering Foundations", "level": "Beginner", "topics": [
                {"title": "SQL Mastery", "desc": "Window functions, CTEs, performance tuning.", "url": "https://mode.com/sql-tutorial/", "type": "Course", "hours": 5},
                {"title": "Python for Data Engineering", "desc": "File I/O, pandas, data manipulation.", "url": "https://realpython.com/", "type": "Article", "hours": 4},
                {"title": "Data Modeling", "desc": "Star schema, snowflake, normalization.", "url": "https://www.youtube.com/watch?v=lWPiSZf7-uQ", "type": "Video", "hours": 4},
            ]},
            {"week": 2, "title": "ETL & Data Pipelines", "level": "Intermediate", "topics": [
                {"title": "Apache Airflow", "desc": "DAGs, operators, scheduling.", "url": "https://airflow.apache.org/docs/apache-airflow/stable/tutorial/", "type": "Documentation", "hours": 5},
                {"title": "ETL Best Practices", "desc": "Idempotency, data quality checks.", "url": "https://www.youtube.com/watch?v=oF5uE_0kOdg", "type": "Video", "hours": 3},
            ]},
            {"week": 3, "title": "Data Warehousing", "level": "Intermediate", "topics": [
                {"title": "BigQuery / Snowflake / Redshift", "desc": "Cloud data warehouse platforms.", "url": "https://cloud.google.com/bigquery/docs", "type": "Documentation", "hours": 5},
                {"title": "dbt (Data Build Tool)", "desc": "Transformations in the warehouse.", "url": "https://docs.getdbt.com/docs/introduction", "type": "Documentation", "hours": 4},
            ]},
            {"week": 4, "title": "Big Data Technologies", "level": "Advanced", "topics": [
                {"title": "Apache Spark", "desc": "Distributed data processing.", "url": "https://spark.apache.org/docs/latest/quick-start.html", "type": "Documentation", "hours": 5},
                {"title": "Apache Kafka", "desc": "Real-time event streaming.", "url": "https://kafka.apache.org/documentation/", "type": "Documentation", "hours": 5},
                {"title": "Data Lake Architecture", "desc": "Delta Lake, Iceberg, partitioning.", "url": "https://delta.io/", "type": "Documentation", "hours": 4},
            ]},
            {"week": 5, "title": "Cloud & Orchestration", "level": "Advanced", "topics": [
                {"title": "AWS Glue & EMR", "desc": "Managed ETL and Spark on AWS.", "url": "https://docs.aws.amazon.com/glue/", "type": "Documentation", "hours": 4},
                {"title": "Docker & Kubernetes for DE", "desc": "Containerized pipeline deployments.", "url": "https://docs.docker.com/get-started/", "type": "Documentation", "hours": 4},
                {"title": "Data Engineering Interview Prep", "desc": "SQL problems, system design for DE.", "url": "https://www.youtube.com/watch?v=X2CQ14YM5Wk", "type": "Video", "hours": 4},
            ]},
        ]
    },
    {
        "name": "Blockchain Developer",
        "slug": "blockchain-developer",
        "icon": "bi-link-45deg",
        "description": "Build decentralized applications (dApps) and smart contracts on blockchain platforms.",
        "estimated_weeks": 10,
        "difficulty": "Advanced",
        "milestones": [
            {"week": 1, "title": "Blockchain Fundamentals", "level": "Beginner", "topics": [
                {"title": "How Blockchain Works", "desc": "Blocks, hashing, consensus, decentralization.", "url": "https://www.youtube.com/watch?v=SSo_EIwHSd4", "type": "Video", "hours": 3},
                {"title": "Cryptography Basics", "desc": "Public/private keys, hashing, digital signatures.", "url": "https://www.khanacademy.org/computing/computer-science/cryptography", "type": "Course", "hours": 4},
                {"title": "Bitcoin & Ethereum Overview", "desc": "How major blockchains work.", "url": "https://ethereum.org/en/developers/docs/", "type": "Documentation", "hours": 3},
            ]},
            {"week": 2, "title": "Solidity Programming", "level": "Beginner", "topics": [
                {"title": "Solidity Basics", "desc": "Data types, functions, modifiers, events.", "url": "https://docs.soliditylang.org/en/latest/", "type": "Documentation", "hours": 5},
                {"title": "Smart Contract Development", "desc": "ERC-20 tokens, access control.", "url": "https://cryptozombies.io/", "type": "Course", "hours": 5},
            ]},
            {"week": 3, "title": "Development Tools", "level": "Intermediate", "topics": [
                {"title": "Hardhat & Foundry", "desc": "Development environments for Ethereum.", "url": "https://hardhat.org/hardhat-runner/docs/getting-started", "type": "Documentation", "hours": 4},
                {"title": "Testing Smart Contracts", "desc": "Unit tests, fuzzing, coverage.", "url": "https://docs.openzeppelin.com/", "type": "Documentation", "hours": 4},
                {"title": "Web3.js & Ethers.js", "desc": "Interacting with contracts from JavaScript.", "url": "https://docs.ethers.org/v6/", "type": "Documentation", "hours": 4},
            ]},
            {"week": 4, "title": "DeFi & NFTs", "level": "Intermediate", "topics": [
                {"title": "DeFi Protocols", "desc": "AMMs, lending, staking concepts.", "url": "https://www.youtube.com/watch?v=17QRFlml4pA", "type": "Video", "hours": 4},
                {"title": "NFT Development", "desc": "ERC-721, ERC-1155, metadata, IPFS.", "url": "https://docs.openzeppelin.com/contracts/5.x/erc721", "type": "Documentation", "hours": 4},
            ]},
            {"week": 5, "title": "Security & Deployment", "level": "Advanced", "topics": [
                {"title": "Smart Contract Security", "desc": "Reentrancy, front-running, auditing.", "url": "https://consensys.github.io/smart-contract-best-practices/", "type": "Article", "hours": 5},
                {"title": "Mainnet Deployment", "desc": "Deploying to Ethereum/Polygon.", "url": "https://hardhat.org/hardhat-runner/docs/guides/deploying", "type": "Documentation", "hours": 3},
                {"title": "dApp Frontend", "desc": "Connect React to smart contracts.", "url": "https://wagmi.sh/", "type": "Documentation", "hours": 4},
            ]},
        ]
    },
    {
        "name": "AI Research Scientist",
        "slug": "ai-research-scientist",
        "icon": "bi-lightbulb",
        "description": "Advance the field of artificial intelligence through research, experimentation, and publication.",
        "estimated_weeks": 12,
        "difficulty": "Advanced",
        "milestones": [
            {"week": 1, "title": "Mathematical Foundations", "level": "Beginner", "topics": [
                {"title": "Linear Algebra", "desc": "Vectors, matrices, eigenvalues, SVD.", "url": "https://www.youtube.com/playlist?list=PLZHQObOWTQDPD3MizzM2xVFitgF8hE_ab", "type": "Video", "hours": 5},
                {"title": "Probability & Statistics", "desc": "Bayesian inference, distributions, MLE.", "url": "https://www.khanacademy.org/math/statistics-probability", "type": "Course", "hours": 5},
                {"title": "Calculus & Optimization", "desc": "Gradients, chain rule, convex optimization.", "url": "https://www.youtube.com/playlist?list=PLZHQObOWTQDMsr9K-rj53DwVRMYO3t5Yr", "type": "Video", "hours": 5},
            ]},
            {"week": 2, "title": "Machine Learning Theory", "level": "Intermediate", "topics": [
                {"title": "Statistical Learning Theory", "desc": "Bias-variance, PAC learning, VC dimension.", "url": "https://www.youtube.com/watch?v=rqJ8SrnmWu0", "type": "Video", "hours": 5},
                {"title": "Probabilistic Models", "desc": "GMMs, HMMs, graphical models.", "url": "https://www.youtube.com/watch?v=TCYRwlpJx2c", "type": "Video", "hours": 5},
            ]},
            {"week": 3, "title": "Deep Learning Theory", "level": "Intermediate", "topics": [
                {"title": "Neural Network Architectures", "desc": "CNNs, RNNs, LSTMs, attention.", "url": "https://www.deeplearningbook.org/", "type": "Article", "hours": 6},
                {"title": "Optimization Methods", "desc": "SGD, Adam, learning rate scheduling.", "url": "https://ruder.io/optimizing-gradient-descent/", "type": "Article", "hours": 4},
                {"title": "Regularization Techniques", "desc": "Dropout, batch norm, data augmentation.", "url": "https://cs231n.github.io/neural-networks-2/", "type": "Article", "hours": 3},
            ]},
            {"week": 4, "title": "Transformers & LLMs", "level": "Advanced", "topics": [
                {"title": "Attention Mechanism", "desc": "Self-attention, multi-head attention, positional encoding.", "url": "https://jalammar.github.io/illustrated-transformer/", "type": "Article", "hours": 5},
                {"title": "Large Language Models", "desc": "GPT, BERT, T5 architectures.", "url": "https://huggingface.co/learn/nlp-course/", "type": "Course", "hours": 5},
                {"title": "Fine-Tuning & RLHF", "desc": "LoRA, PEFT, reinforcement learning from human feedback.", "url": "https://huggingface.co/docs/trl/", "type": "Documentation", "hours": 5},
            ]},
            {"week": 5, "title": "Research Methodology", "level": "Advanced", "topics": [
                {"title": "Reading Research Papers", "desc": "How to read and critique ML papers.", "url": "https://www.youtube.com/watch?v=SHTOI0KtZnU", "type": "Video", "hours": 3},
                {"title": "Experiment Design", "desc": "Ablation studies, baselines, reproducibility.", "url": "https://arxiv.org/", "type": "Article", "hours": 4},
                {"title": "Academic Writing", "desc": "LaTeX, paper structure, conferences.", "url": "https://www.overleaf.com/learn", "type": "Article", "hours": 4},
            ]},
            {"week": 6, "title": "Generative AI", "level": "Advanced", "topics": [
                {"title": "GANs", "desc": "Generator-discriminator training, StyleGAN.", "url": "https://papers.nips.cc/paper/2014/hash/5ca3e9b122f61f8f06494c97b1afccf3-Abstract.html", "type": "Article", "hours": 5},
                {"title": "Diffusion Models", "desc": "DDPM, Stable Diffusion, score matching.", "url": "https://lilianweng.github.io/posts/2021-07-11-diffusion-models/", "type": "Article", "hours": 5},
                {"title": "Multimodal AI", "desc": "CLIP, DALL-E, vision-language models.", "url": "https://openai.com/research/clip", "type": "Article", "hours": 4},
            ]},
        ]
    },
]
