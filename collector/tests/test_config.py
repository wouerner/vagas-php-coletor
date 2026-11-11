"""Configuração dos coletores (config.py): a linguagem e os termos vêm da base, e o mesmo
filtro vale para qualquer linguagem."""

import pytest

from vagas import classify, config

RUBY = {
    "language": {"name": "Ruby", "slug": "ruby", "examples": "Ruby, Rails ou Sinatra"},
    "core": r"\b(ruby|rails|sinatra)\b",
    "stack": [["Ruby", r"\bruby\b"], ["Rails", r"\brails\b"]],
}


@pytest.fixture
def ruby():
    config.load(RUBY)
    yield
    config.load({})


def test_defaults_are_php():
    assert classify.is_relevant_job("Desenvolvedor Laravel Pleno")
    assert not classify.is_relevant_job("Desenvolvedor Ruby on Rails")
    assert list(classify.STACK)[:3] == ["PHP", "Laravel", "Symfony"]


def test_language_comes_from_config(ruby):
    assert classify.is_relevant_job("Desenvolvedor Ruby on Rails")
    assert not classify.is_relevant_job("Desenvolvedor Laravel Pleno")
    assert classify.job_verdict("Desenvolvedor Laravel Pleno") == "no_lang"
    assert classify.details("Dev Rails Sênior", "Ruby 3")["stack"] == "Ruby,Rails"
    assert classify.is_hiring_post("Estamos contratando pessoa desenvolvedora Ruby, remoto")
    rules = {r["id"]: r for r in classify.RULES}
    assert rules["lang_title"]["title"].startswith("Ruby")
    assert rules["lang_title"]["patterns"] == [RUBY["core"]]


def test_missing_keys_keep_defaults(ruby):
    assert config.get("search") == config.defaults("php")["search"]
    assert classify.SELF_AUTHOR == config.defaults("php")["self_author"]


def test_env_overrides_search(monkeypatch):
    assert config.search("gupy", "VAGAS_GUPY_TERMS") == config.defaults("php")["search"]["gupy"]
    monkeypatch.setenv("VAGAS_GUPY_TERMS", " ruby , rails ,")
    assert config.search("gupy", "VAGAS_GUPY_TERMS") == ["ruby", "rails"]
    monkeypatch.setenv("VAGAS_GUPY_TERMS", "")
    assert config.search("gupy", "VAGAS_GUPY_TERMS") == config.defaults("php")["search"]["gupy"]


def test_ruby_tenant_defaults():
    try:
        config.load({}, "ruby")
        assert config.tenant == "ruby"
        assert classify.is_relevant_job("Pessoa Desenvolvedora Ruby on Rails Sênior")
        assert classify.is_relevant_job("Backend Developer (Rails)")
        assert not classify.is_relevant_job("Desenvolvedor PHP Laravel")
        # "Ruby on Rails" é uma menção só: uma vez na descrição não basta.
        assert not classify.is_relevant_job("Backend Engineer", "Kotlin. Familiarity with Ruby on Rails.")
        assert classify.is_relevant_job("Backend Engineer", "Ruby on Rails. Testes em Ruby.")
        assert classify.details("Dev Rails", "Ruby, Sidekiq e RSpec")["stack"] == "Ruby,Rails,Sidekiq,RSpec"
        assert config.search("programathor", "VAGAS_PROGRAMATHOR_PAGES") == ["jobs-ruby", "jobs-ruby-on-rails"]
    finally:
        config.load({}, "php")
    assert config.tenant == "php"
    assert classify.is_relevant_job("Desenvolvedor PHP Laravel")


def test_lua_tenant_defaults():
    try:
        config.load({}, "lua")
        assert config.tenant == "lua"
        assert classify.is_relevant_job("Desenvolvedor Lua Sênior")
        assert classify.is_relevant_job("Backend Engineer (OpenResty)")
        assert classify.is_relevant_job("Roblox Developer")
        assert not classify.is_relevant_job("Desenvolvedor PHP Laravel")
        assert not classify.is_relevant_job("Backend Engineer", "Go e Kubernetes. Scripts em Lua.")
        assert classify.is_relevant_job("Backend Engineer", "Lua no gateway. LuaJIT e OpenResty.")
        assert classify.details("Dev Lua", "LuaJIT, OpenResty e Nginx")["stack"] == "Lua,LuaJIT,OpenResty,Nginx"
        assert config.search("programathor", "VAGAS_PROGRAMATHOR_PAGES") == ["jobs-lua"]
    finally:
        config.load({}, "php")
    assert config.tenant == "php"
    assert classify.is_relevant_job("Desenvolvedor PHP Laravel")


def test_java_tenant_defaults():
    try:
        config.load({}, "java")
        assert config.tenant == "java"
        assert classify.is_relevant_job("Desenvolvedor Java Sênior")
        assert classify.is_relevant_job("Backend Developer (Spring Boot)")
        assert classify.is_relevant_job("Engenheiro de Software Quarkus")
        assert classify.is_relevant_job("Backend Engineer", "Micronaut e Hibernate. APIs em Jakarta EE.")
        # JavaScript não é Java.
        assert not classify.is_relevant_job("Desenvolvedor JavaScript Pleno")
        assert not classify.is_relevant_job("Desenvolvedor Java Script Pleno")
        assert not classify.is_relevant_job("Desenvolvedor PHP Laravel")
        assert not classify.is_relevant_job("Frontend Engineer", "React e JavaScript. Backend em Java.")
        assert (classify.details("Dev Java", "Spring Boot, Spring Cloud, Hibernate e Jakarta EE")["stack"]
                == "Java,Spring Boot,Spring,Jakarta EE,Hibernate")
        assert classify.details("Dev JavaScript", "Node")["stack"] is None
        assert config.search("programathor", "VAGAS_PROGRAMATHOR_PAGES") == [
            "jobs-java", "jobs-spring-boot", "jobs-spring", "jobs-hibernate"]
        assert config.search("gupy", "VAGAS_GUPY_TERMS") == [
            "java", "spring boot", "spring", "quarkus", "micronaut", "jakarta ee", "hibernate"]
    finally:
        config.load({}, "php")
    assert config.tenant == "php"
    assert classify.is_relevant_job("Desenvolvedor PHP Laravel")
    assert not classify.is_relevant_job("Desenvolvedor Java Spring Boot")


def test_python_tenant_defaults():
    try:
        config.load({}, "python")
        assert config.tenant == "python"
        assert classify.is_relevant_job("Desenvolvedor Python Sênior")
        assert classify.is_relevant_job("Backend Developer (Django)")
        assert classify.is_relevant_job("Engenheiro de Software Python3/FastAPI")
        assert classify.is_relevant_job("Pessoa Desenvolvedora Fast API Pleno")
        assert classify.is_relevant_job("Backend Engineer", "APIs em Flask e Django, com Celery.")
        assert not classify.is_relevant_job("Desenvolvedor PHP Laravel")
        # Python citado uma vez só, ou em vaga que não é de desenvolvimento, não entra.
        assert not classify.is_relevant_job("Frontend Engineer", "React e TypeScript. Scripts em Python.")
        assert not classify.is_relevant_job("Analista de Dados", "Python, pandas e SQL. Python avançado.")
        assert not classify.is_relevant_job("Analista de BI", "PySpark e Power BI.")
        assert (classify.details("Dev Python", "Django, Fast API, Celery, SQLAlchemy e pytest")["stack"]
                == "Python,Django,FastAPI,Celery,SQLAlchemy,Pytest")
        assert classify.details("Analista de BI", "PySpark")["stack"] is None
        assert config.search("programathor", "VAGAS_PROGRAMATHOR_PAGES") == [
            "jobs-python", "jobs-django", "jobs-flask"]
        assert config.search("gupy", "VAGAS_GUPY_TERMS") == ["python", "django", "flask", "fastapi"]
    finally:
        config.load({}, "php")
    assert config.tenant == "php"
    assert classify.is_relevant_job("Desenvolvedor PHP Laravel")
    assert not classify.is_relevant_job("Desenvolvedor Python Django")


def test_nodejs_tenant_defaults():
    try:
        config.load({}, "nodejs")
        assert config.tenant == "nodejs"
        assert classify.is_relevant_job("Desenvolvedor Node.js Sênior")
        assert classify.is_relevant_job("Pessoa Desenvolvedora NodeJS Pleno")
        # Título vindo do endereço da vaga (Programathor, Nerdin...): "node-js" vira "node js".
        assert classify.is_relevant_job("desenvolvedor node js pleno")
        assert classify.is_relevant_job("Backend Developer (NestJS)")
        assert classify.is_relevant_job("Desenvolvedor Backend Node Pleno")
        assert classify.is_relevant_job("Full Stack Developer (Node + React)")
        assert classify.is_relevant_job("Backend Engineer", "APIs em Fastify e Express.js, com TypeScript.")
        # Front-end e JavaScript em geral não são Node.js.
        assert not classify.is_relevant_job("Desenvolvedor Front-end React")
        assert not classify.is_relevant_job("Desenvolvedor JavaScript Pleno")
        assert not classify.is_relevant_job("Desenvolvedor React Native", "React, TypeScript e Next.js.")
        assert not classify.is_relevant_job("Frontend Engineer", "React e TypeScript. Backend em Node.js.")
        # "node" sozinho é ambíguo: nó de Kubernetes, de rede, de blockchain.
        assert not classify.is_relevant_job("Kubernetes Node Administrator")
        assert not classify.is_relevant_job(
            "DevOps Engineer", "Cada worker node do cluster Kubernetes roda o node exporter. Node pools na AWS.")
        assert not classify.is_relevant_job("Desenvolvedor PHP Laravel")
        assert not classify.is_relevant_job("Desenvolvedor Java Spring Boot")
        assert (classify.details("Dev Node.js", "NestJS, Express, Fastify e TypeScript")["stack"]
                == "Node.js,Express,NestJS,Fastify,TypeScript")
        assert classify.details("Dev Backend Node", "AdonisJS e Koa")["stack"] == "Node.js,AdonisJS,Koa"
        assert classify.details("Dev React", "Cartão American Express")["stack"] is None
        assert config.search("programathor", "VAGAS_PROGRAMATHOR_PAGES") == [
            "jobs-node-js", "jobs-nest-js", "jobs-express", "jobs-adonis-js", "jobs-koa"]
        assert config.search("gupy", "VAGAS_GUPY_TERMS") == [
            "node.js", "nodejs", "node", "nestjs", "express.js", "fastify", "adonisjs"]
        rules = {r["id"]: r for r in classify.RULES}
        assert rules["lang_title"]["title"].startswith("Node.js")
    finally:
        config.load({}, "php")
    assert config.tenant == "php"
    assert classify.is_relevant_job("Desenvolvedor PHP Laravel")
    assert not classify.is_relevant_job("Desenvolvedor Node.js")


def test_dotnet_tenant_defaults():
    try:
        config.load({}, "dotnet")
        assert config.tenant == "dotnet"
        assert classify.is_relevant_job("Desenvolvedor .NET Sênior")
        assert classify.is_relevant_job("Desenvolvedor C# Pleno")
        assert classify.is_relevant_job("Pessoa Desenvolvedora C#/.NET")
        assert classify.is_relevant_job("Backend Developer (ASP.NET Core)")
        assert classify.is_relevant_job("Desenvolvedor Dotnet Júnior")
        assert classify.is_relevant_job("Programador VB.NET")
        # Título vindo do endereço da vaga (Programathor, Nerdin...): sem "#" nem ponto.
        assert classify.is_relevant_job("desenvolvedor c sharp pleno")
        assert classify.is_relevant_job("desenvolvedor net senior")
        assert classify.is_relevant_job("Backend Engineer", "APIs em ASP.NET Core com Entity Framework e Blazor.")
        # "\b" não casa em volta de "#" e ".": C e C++ não são C#, e ".net" de endereço não conta.
        assert not classify.is_relevant_job("Desenvolvedor C Embarcado")
        assert not classify.is_relevant_job("Desenvolvedor C++ Sênior")
        assert not classify.is_relevant_job("Analista de Redes", "Acesse empresa.net e www.provedor.net/vagas.")
        assert not classify.is_relevant_job("Analista de Marketing", "Net promoter score e internet.")
        assert not classify.is_relevant_job("Desenvolvedor PHP Laravel")
        assert not classify.is_relevant_job("Desenvolvedor Java Spring Boot")
        assert not classify.is_relevant_job("Frontend Engineer", "React e TypeScript. Backend em .NET.")
        assert (classify.details("Dev .NET", "C#, ASP.NET Core, Entity Framework e Blazor")["stack"]
                == ".NET,C#,ASP.NET,Blazor,Entity Framework")
        assert classify.details("Dev C Sharp", "Xamarin, .NET MAUI, WPF, F# e VB.NET")["stack"] == (
            ".NET,C#,MAUI,Xamarin,WPF,F#,VB.NET")
        assert classify.details("Dev C++", "Linux embarcado")["stack"] is None
        assert config.search("programathor", "VAGAS_PROGRAMATHOR_PAGES")[:3] == [
            "jobs-net", "jobs-c-sharp", "jobs-asp-net"]
        assert config.search("gupy", "VAGAS_GUPY_TERMS") == [
            "c#", ".net", "dotnet", "asp.net", "blazor", "entity framework"]
        assert config.search("github", "VAGAS_GITHUB_REPOS") == ["dotnetdevbr/vagas", "backend-br/vagas"]
        rules = {r["id"]: r for r in classify.RULES}
        assert rules["lang_title"]["title"].startswith(".NET")
    finally:
        config.load({}, "php")
    assert config.tenant == "php"
    assert classify.is_relevant_job("Desenvolvedor PHP Laravel")
    assert not classify.is_relevant_job("Desenvolvedor .NET")


def test_go_tenant_defaults():
    try:
        config.load({}, "go")
        assert config.tenant == "go"
        assert classify.is_relevant_job("Desenvolvedor Golang Sênior")
        assert classify.is_relevant_job("Golang Engineer")
        assert classify.is_relevant_job("Desenvolvedor Go")
        assert classify.is_relevant_job("Go Developer")
        assert classify.is_relevant_job("Senior Go Engineer")
        assert classify.is_relevant_job("Engenheiro de Software Go")
        assert classify.is_relevant_job("Backend Go")
        assert classify.is_relevant_job("Dev Go Pleno")
        assert classify.is_relevant_job("Desenvolvedor(a) Go Sênior")
        assert classify.is_relevant_job("Desenvolvedor Backend Sênior Go")
        assert classify.is_relevant_job("Pessoa Desenvolvedora Backend (Go)")
        assert classify.is_relevant_job("Software Engineer - Go (Golang)")
        # Título vindo do endereço da vaga (Programathor, Nerdin...): minúsculas, sem pontuação.
        assert classify.is_relevant_job("desenvolvedor go pleno")
        assert classify.is_relevant_job("senior golang developer")
        assert classify.is_relevant_job("desenvolvedor go lang")
        assert classify.is_relevant_job("Backend Engineer", "Microsserviços em Go com gin-gonic, GORM e goroutines.")
        assert classify.is_relevant_job("Backend Engineer", "Services written in Go. Echo framework and gRPC.")
        # "go" é palavra comum: sozinho, só conta colado a um cargo de desenvolvimento.
        assert not classify.is_relevant_job("Go-to-Market Manager")
        assert not classify.is_relevant_job("Software Engineer, Go-to-Market")
        assert not classify.is_relevant_job("Go Live Engineer")
        assert not classify.is_relevant_job("Let's go! Developer wanted")
        assert not classify.is_relevant_job("Pokémon Go Developer Relations")
        assert not classify.is_relevant_job("Desenvolvedor Go Horse")
        assert not classify.is_relevant_job("Google Cloud Developer")
        assert not classify.is_relevant_job("Desenvolvedor Django")
        assert not classify.is_relevant_job("Desenvolvedor MongoDB")
        assert not classify.is_relevant_job("Cargo: Desenvolvedor Hugo")
        assert not classify.is_relevant_job(
            "Software Engineer", "Ready to go? Go live in weeks. Our go-to-market team uses Google, Django and MongoDB.")
        # "GO" depois de travessão é Goiás, e "em GO" (maiúsculas) também.
        assert not classify.is_relevant_job("Desenvolvedor Pleno - GO")
        assert not classify.is_relevant_job("Desenvolvedor Full Stack - Goiânia/GO")
        assert not classify.is_relevant_job("Desenvolvedor Backend", "Vaga presencial em GO. Atuação em GO e no DF.")
        # Gin, Echo e Fiber sozinhos são bebida, eco e fibra.
        assert not classify.is_relevant_job("Bartender", "Gin tônica. Gin importado.")
        assert not classify.is_relevant_job("Engenheiro de Redes", "Fiber optic. Amazon Echo. Fiber to the home.")
        assert not classify.is_relevant_job("Desenvolvedor PHP Laravel")
        assert not classify.is_relevant_job("Desenvolvedor Java Spring Boot")
        assert not classify.is_relevant_job("Frontend Engineer", "React e TypeScript. Backend em Golang.")
        assert (classify.details("Dev Go", "Gin, Echo e Fiber com GORM, gRPC e Kubernetes")["stack"]
                == "Go,Gin,Echo,Fiber,GORM,gRPC,Kubernetes")
        assert classify.details("Golang Developer", "APIs com gin-gonic e k8s")["stack"] == "Go,Gin,Kubernetes"
        assert classify.details("Bartender", "Gin tônica, fiber optic e Amazon Echo")["stack"] is None
        assert classify.details("Go-to-Market Manager", "Go live")["stack"] is None
        assert config.search("programathor", "VAGAS_PROGRAMATHOR_PAGES") == ["jobs-go", "jobs-gin"]
        assert config.search("gupy", "VAGAS_GUPY_TERMS") == ["golang", "desenvolvedor go", "backend go"]
        assert config.search("github", "VAGAS_GITHUB_REPOS") == ["golang-brasil/vagas", "backend-br/vagas"]
        rules = {r["id"]: r for r in classify.RULES}
        assert rules["lang_title"]["title"].startswith("Go")
    finally:
        config.load({}, "php")
    assert config.tenant == "php"
    assert classify.is_relevant_job("Desenvolvedor PHP Laravel")
    assert not classify.is_relevant_job("Desenvolvedor Golang")


def test_mobile_tenant_defaults():
    try:
        config.load({}, "mobile")
        assert config.tenant == "mobile"
        assert classify.is_relevant_job("Desenvolvedor Android Pleno")
        assert classify.is_relevant_job("iOS Developer (Swift)")
        assert classify.is_relevant_job("Desenvolvedor Mobile Flutter")
        assert classify.is_relevant_job("Engenheiro de Software React Native")
        assert classify.is_relevant_job("Desenvolvedor(a) Mobile Sênior")
        assert classify.is_relevant_job("Engenheiro(a) de Software Sênior - Android")
        assert classify.is_relevant_job("Desenvolvedor de Aplicativos Móveis")
        assert classify.is_relevant_job("Desenvolvedor Swift Pleno")
        assert classify.is_relevant_job("Desenvolvedor Kotlin")
        assert classify.is_relevant_job("Kotlin Multiplatform Engineer")
        assert classify.is_relevant_job("Desenvolvedor .NET MAUI")
        # Título vindo do endereço da vaga (Programathor, Nerdin...): minúsculas, sem pontuação.
        assert classify.is_relevant_job("desenvolvedor ios swift")
        assert classify.is_relevant_job("desenvolvedor react native pleno")
        assert classify.is_relevant_job("Software Engineer", "Apps em Kotlin com Jetpack Compose para Android.")
        # Etiqueta de issue do GitHub: o item inteiro.
        assert classify.is_relevant_job("Vaga na Acme", None, "Android,Remoto,PJ")
        assert not classify.is_relevant_job("Vaga na Acme", None, "Mobile first,Remoto")
        # "swift" é palavra inglesa e a rede bancária SWIFT: só conta colado ao cargo.
        assert not classify.is_relevant_job("Analista de Pagamentos SWIFT")
        assert not classify.is_relevant_job("Engenheiro de Software - Pagamentos SWIFT")
        # "mobile", "android" e "ios" sozinhos aparecem em marketing, vendas, suporte e QA.
        assert not classify.is_relevant_job("Mobile Marketing Manager")
        assert not classify.is_relevant_job("Desenvolvedor Web Mobile First")
        assert not classify.is_relevant_job("T-Mobile Software Engineer")
        assert not classify.is_relevant_job("Analista de Mobilidade Urbana")
        assert not classify.is_relevant_job("Vendedor de celulares Android")
        assert not classify.is_relevant_job("Técnico de manutenção iOS")
        assert not classify.is_relevant_job("Suporte Android")
        assert not classify.is_relevant_job("QA Android")
        # React sozinho é web; "compose" e "dart" sozinhos não bastam.
        assert not classify.is_relevant_job("Desenvolvedor React")
        assert not classify.is_relevant_job("docker compose")
        assert not classify.is_relevant_job("DevOps Engineer (Docker Compose)")
        assert not classify.is_relevant_job("Desenvolvedor Dart")
        # Kotlin colado a back-end não é mobile.
        assert not classify.is_relevant_job("Desenvolvedor Backend Kotlin")
        assert not classify.is_relevant_job("Kotlin Backend Engineer")
        assert not classify.is_relevant_job("Desenvolvedor Kotlin/Spring Boot")
        assert not classify.is_relevant_job("Backend Engineer", "API em Go. Temos apps Android e iOS. Mobile first.")
        assert not classify.is_relevant_job("Desenvolvedor PHP Laravel")
        assert not classify.is_relevant_job("Desenvolvedor .NET")
        assert (classify.details("Dev Android", "Kotlin, Jetpack Compose e KMP; Swift e SwiftUI no iOS")["stack"]
                == "Android,iOS,Kotlin,Swift,SwiftUI,Jetpack Compose,Kotlin Multiplatform")
        assert classify.details("Dev Mobile", "Flutter/Dart, React Native e Ionic")["stack"] == (
            "Flutter,React Native,Dart,Ionic")
        assert classify.details("Dev React", "Docker Compose")["stack"] is None
        assert config.search("programathor", "VAGAS_PROGRAMATHOR_PAGES")[:6] == [
            "jobs-android", "jobs-ios", "jobs-kotlin", "jobs-swift", "jobs-flutter", "jobs-react-native"]
        assert config.search("gupy", "VAGAS_GUPY_TERMS") == [
            "android", "ios", "mobile", "kotlin", "swift", "flutter", "react native"]
        assert config.search("linkedin", "VAGAS_LINKEDIN_KEYWORDS")[:3] == [
            "desenvolvedor android", "desenvolvedor ios", "desenvolvedor mobile"]
        assert "backend-br/vagas" not in config.search("github", "VAGAS_GITHUB_REPOS")
        assert config.search("github", "VAGAS_GITHUB_REPOS")[:2] == ["androiddevbr/vagas", "CocoaHeadsBrasil/vagas"]
        rules = {r["id"]: r for r in classify.RULES}
        assert rules["lang_title"]["title"].startswith("Mobile")
    finally:
        config.load({}, "php")
    assert config.tenant == "php"
    assert classify.is_relevant_job("Desenvolvedor PHP Laravel")
    assert not classify.is_relevant_job("Desenvolvedor Android")


def test_frontend_tenant_defaults():
    try:
        config.load({}, "frontend")
        assert config.tenant == "frontend"
        assert classify.is_relevant_job("Desenvolvedor Front-end React Pleno")
        assert classify.is_relevant_job("Frontend Engineer (Vue.js)")
        assert classify.is_relevant_job("Angular Developer")
        assert classify.is_relevant_job("Pessoa Desenvolvedora Front-End Sênior")
        assert classify.is_relevant_job("Desenvolvedor(a) React")
        assert classify.is_relevant_job("Software Engineer - Next.js")
        assert classify.is_relevant_job("Desenvolvedor Nuxt")
        assert classify.is_relevant_job("SvelteKit Engineer")
        # Título vindo do endereço da vaga (Programathor, Nerdin...): sem hífen nem ponto.
        assert classify.is_relevant_job("desenvolvedor front end react")
        assert classify.is_relevant_job("desenvolvedor react pleno")
        assert classify.is_relevant_job("dev vue js")
        assert classify.is_relevant_job("desenvolvedor next js")
        assert classify.is_relevant_job("Desenvolvedor Pleno", "Experiência com React e TypeScript. Testes com React Testing Library.")
        # JavaScript sozinho não é front-end (Node.js também é JavaScript).
        assert not classify.is_relevant_job("Desenvolvedor JavaScript")
        # Palavras comuns: "react" e "next" em inglês, "vue" em francês, "angular" adjetivo.
        assert not classify.is_relevant_job("Software Engineer", "We react to incidents and react to changes. Next steps.")
        assert not classify.is_relevant_job("Engenheiro de Software", "Momento angular e velocidade angular.")
        assert not classify.is_relevant_job("Développeur", "En vue de la mission, point de vue produit.")
        assert not classify.is_relevant_job("Next Step Manager")
        # React Native é do tenant mobile: não conta como React, nem no filtro de stack.
        assert not classify.is_relevant_job("Desenvolvedor Web", "React Native e React Native CLI.")
        assert classify.details("Dev", "React Native")["stack"] is None
        assert classify.job_verdict("UX Designer") == "not_dev"
        assert not classify.is_relevant_job("Desenvolvedor PHP Laravel")
        assert (classify.details("Dev Front-end", "React, Vue.js 3, Angular, Next.js, Nuxt e SvelteKit")["stack"]
                == "React,Vue.js,Angular,Next.js,Nuxt,Svelte")
        assert classify.details("Dev React", "TypeScript, JavaScript, Tailwind CSS e Redux")["stack"] == (
            "React,TypeScript,JavaScript,Tailwind,Redux")
        assert config.search("programathor", "VAGAS_PROGRAMATHOR_PAGES")[:4] == [
            "jobs-front-end", "jobs-react", "jobs-vue-js", "jobs-angular"]
        assert config.search("gupy", "VAGAS_GUPY_TERMS") == [
            "front-end", "frontend", "react", "reactjs", "vue.js", "vuejs", "angular", "next.js"]
        assert config.search("github", "VAGAS_GITHUB_REPOS") == ["frontendbr/vagas", "react-brasil/vagas"]
        rules = {r["id"]: r for r in classify.RULES}
        assert rules["lang_title"]["title"].startswith("Front-end")
    finally:
        config.load({}, "php")
    assert config.tenant == "php"
    assert classify.is_relevant_job("Desenvolvedor PHP Laravel")
    assert not classify.is_relevant_job("Desenvolvedor Front-end React")


def test_exclude_refuses_by_title_before_the_language_rules():
    try:
        config.load({}, "frontend")
        assert classify.EXCLUDE.pattern == config.get("exclude")
        for title in ("Desenvolvedor Front-end React Pleno", "Frontend Engineer (Vue.js)",
                      "Angular Developer", "desenvolvedor front end react"):
            assert classify.job_verdict(title) == "lang_title", title
        # Full stack, back-end e mobile ficam de fora mesmo citando React, Vue ou Angular;
        # título com os dois ("Front-end ou Full Stack") também: a vaga não é só de front-end.
        for title in ("Desenvolvedor Full Stack React/Node", "Fullstack Developer (Angular + Java)",
                      "Desenvolvedor React Native", "Desenvolvedor Backend Node",
                      "Desenvolvedor Backend Node com React", "Front-end ou Full Stack",
                      "Desenvolvedor Frontend/Backend", "Desenvolvedor Java/Angular",
                      "Desenvolvedor Flutter", "Desenvolvedor iOS", "desenvolvedor react native pleno",
                      "Full-Stack Engineer (Vue.js)"):
            assert classify.job_verdict(title) == "excluded", title
            assert not classify.is_relevant_job(title, "Front-end com React. React e Vue.js.", "front-end")
        assert classify.job_verdict("UX Designer") == "not_dev"  # a regra de cargo vem antes
        # A exclusão é pelo título: o back-end citado na descrição não barra.
        assert classify.is_relevant_job("Desenvolvedor Front-end", "Integração com o time de back-end e full stack.")
        ids = [r["id"] for r in classify.RULES]
        assert ids[:3] == ["not_dev", "excluded", "lang_title"]
        assert ids.index("post_excluded") == ids.index("post_no_lang") + 1
        rules = {r["id"]: r for r in classify.RULES}
        assert rules["excluded"]["effect"] == rules["post_excluded"]["effect"] == "recusa"
        assert rules["excluded"]["patterns"] == [config.get("exclude")]
    finally:
        config.load({}, "php")


def test_exclude_on_posts_uses_the_job_title_lines():
    try:
        config.load({}, "frontend")
        full = "Estamos contratando!\nDesenvolvedor Full Stack React Pleno | Remoto\nRequisitos: React e Node"
        front = "Estamos contratando!\nDesenvolvedor Front-end React Pleno | Remoto\nRequisitos: React e TypeScript"
        assert classify.post_verdict(full) == "post_excluded"
        assert not classify.is_hiring_post(full)
        assert classify.is_hiring_post(front)
        # Um título dentro do escopo e outro fora: o post anuncia as duas vagas e continua.
        assert classify.is_hiring_post(front + "\nDesenvolvedor Full Stack React Sênior | Remoto")
        assert classify.is_hiring_post(front + "\nIntegração com o time de back-end (remoto)")
        # Texto corrido, sem linha de título: "full stack" no meio da frase não barra.
        assert classify.is_hiring_post(
            "Estamos contratando pessoa desenvolvedora front-end com React para atuar junto ao time full "
            "stack da empresa, em projetos grandes e com muita autonomia, num ambiente colaborativo, com "
            "benefícios, plano de carreira e aprendizado contínuo para todo o time de tecnologia.")
    finally:
        config.load({}, "php")


def test_tenant_without_exclude_behaves_as_before():
    # Os outros tenants não têm o item (nem precisam): nada é excluído e a regra não é publicada.
    for name in ("php", "ruby", "lua", "java", "python", "nodejs", "dotnet"):
        assert "exclude" not in config.defaults(name)
    try:
        config.load({}, "nodejs")
        assert config.get("exclude") is None and classify.EXCLUDE is None
        assert classify.job_verdict("Desenvolvedor Full Stack Node.js") == "lang_title"
        assert classify.is_relevant_job("Desenvolvedor Backend Node")
        assert classify.is_hiring_post("Estamos contratando!\nDesenvolvedor Full Stack Node.js Pleno | Remoto")
        assert not {"excluded", "post_excluded"} & {r["id"] for r in classify.RULES}
        # Configuração gravada na base antes de o item existir (só os cinco itens de sempre).
        config.load({k: v for k, v in config.defaults("nodejs").items()}, "nodejs")
        assert classify.EXCLUDE is None
        # O item vale para qualquer tenant que o grave na base; vazio desliga.
        config.load({"exclude": r"\bfull[\s-]?stack\b"}, "nodejs")
        assert classify.job_verdict("Desenvolvedor Full Stack Node.js") == "excluded"
        assert classify.job_verdict("Desenvolvedor Node.js") == "lang_title"
        assert "excluded" in {r["id"] for r in classify.RULES}
        config.load({"exclude": ""}, "nodejs")
        assert classify.EXCLUDE is None
        assert classify.is_relevant_job("Desenvolvedor Full Stack Node.js")
        # A exclusão de um tenant não vaza para o seguinte no mesmo processo.
        config.load({}, "frontend")
        assert classify.EXCLUDE is not None
        config.load({}, "ruby")
        assert classify.EXCLUDE is None
    finally:
        config.load({}, "php")
    assert classify.EXCLUDE is None
    assert classify.is_relevant_job("Desenvolvedor Full Stack PHP")


def test_unknown_tenant_never_inherits_another():
    with pytest.raises(ValueError, match="sem configuração"):
        config.load({"language": RUBY["language"]}, "elixir")
    assert config.tenant == "php"  # a configuração anterior continua valendo
    assert classify.is_relevant_job("Desenvolvedor PHP Laravel")


def test_env_terms_only_for_default_tenant(monkeypatch):
    monkeypatch.setenv("VAGAS_GUPY_TERMS", "php,laravel")
    try:
        config.load({}, "ruby")
        assert config.search("gupy", "VAGAS_GUPY_TERMS") == ["ruby", "rails"]
    finally:
        config.load({}, "php")
    assert config.search("gupy", "VAGAS_GUPY_TERMS") == ["php", "laravel"]
